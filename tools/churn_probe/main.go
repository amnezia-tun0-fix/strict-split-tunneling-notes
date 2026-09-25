// churn_probe measures how new flows through the tunnel affect everyone else.
//
// It reproduces the measurement from the review of amneziawg-go#199: TCP connect
// times through the tunnel while another process opens new UDP flows at a fixed
// rate. With the owner lookup on the tun reader, a few hundred new flows per
// second slowed every connection; with it off the reader, they should not.
//
// Build:  GOOS=android GOARCH=arm64 CGO_ENABLED=0 go build -o churn_probe .
// Run from `adb shell` (/data/local/tmp), two processes at once:
//
//	churn_probe flows   -rate 1000 -dur 60s [-hold 2s] [-dst 192.0.2.1:9] [-bind tun0]
//	churn_probe connect -n 40 [-dst 1.1.1.1:443] [-timeout 5s] [-bind tun0]
//	churn_probe dns     -rate 1000 -dur 10s [-dst 1.1.1.1:53] [-wait 2s] [-bind tun0]
//
// flows opens a fresh unconnected UDP socket per flow and sends one datagram:
// every one is a new source port, so a new flow for the filter. By default the
// socket is closed at once, so its owner is often gone by the time it is looked
// up, the platform's most expensive answer. -hold keeps each socket open that
// long, so every owner resolves. The default destination is TEST-NET-1, which
// the server drops. -bind tun0 binds the sockets to the tunnel
// (SO_BINDTODEVICE), as an app outside the VPN would to bypass it.
package main

import (
	"context"
	"flag"
	"fmt"
	"net"
	"os"
	"sort"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: churn_probe flows|connect|dns [flags]")
		os.Exit(2)
	}
	switch os.Args[1] {
	case "flows":
		flows(os.Args[2:])
	case "connect":
		connect(os.Args[2:])
	case "dns":
		dns(os.Args[2:])
	default:
		fmt.Fprintln(os.Stderr, "unknown mode", os.Args[1])
		os.Exit(2)
	}
}

// bindControl returns a socket Control function that binds to dev, or nil.
func bindControl(dev string) func(network, address string, c syscall.RawConn) error {
	if dev == "" {
		return nil
	}
	return func(network, address string, c syscall.RawConn) error {
		var serr error
		if err := c.Control(func(fd uintptr) {
			serr = syscall.SetsockoptString(int(fd), syscall.SOL_SOCKET, syscall.SO_BINDTODEVICE, dev)
		}); err != nil {
			return err
		}
		return serr
	}
}

func flows(args []string) {
	fs := flag.NewFlagSet("flows", flag.ExitOnError)
	rate := fs.Int("rate", 100, "new flows per second")
	dur := fs.Duration("dur", 60*time.Second, "how long to run")
	dst := fs.String("dst", "192.0.2.1:9", "destination of the datagrams")
	bind := fs.String("bind", "", "device to bind the sockets to, e.g. tun0")
	hold := fs.Duration("hold", 0, "keep each socket open this long after sending")
	fs.Parse(args)

	to, err := net.ResolveUDPAddr("udp4", *dst)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	lc := net.ListenConfig{Control: bindControl(*bind)}
	payload := []byte("churn")

	// Tick every millisecond and open as many flows as the rate owes by now,
	// so high rates are not limited by timer resolution.
	start := time.Now()
	deadline := start.Add(*dur)
	sent, failed := 0, 0
	ticker := time.NewTicker(time.Millisecond)
	defer ticker.Stop()
	for now := range ticker.C {
		if now.After(deadline) {
			break
		}
		owed := int(float64(*rate) * now.Sub(start).Seconds())
		for sent+failed < owed {
			if sendOne(lc, to, payload, *hold) {
				sent++
			} else {
				failed++
			}
		}
	}
	elapsed := time.Since(start).Seconds()
	fmt.Printf("flows: rate %d/s asked, %.0f/s done (%d sent, %d failed in %.1fs, hold %v)\n",
		*rate, float64(sent)/elapsed, sent, failed, elapsed, *hold)
	time.Sleep(*hold) // let the last sockets close
}

// sendOne opens a socket, sends one datagram from it and closes it, at once or
// after hold.
func sendOne(lc net.ListenConfig, to net.Addr, payload []byte, hold time.Duration) bool {
	pc, err := lc.ListenPacket(context.Background(), "udp4", ":0")
	if err != nil {
		return false
	}
	_, err = pc.WriteTo(payload, to)
	if hold > 0 {
		time.AfterFunc(hold, func() { pc.Close() })
	} else {
		pc.Close()
	}
	return err == nil
}

// dns opens new flows at a fixed rate that each expect an answer: a DNS query
// from a fresh socket. It counts how many were answered, which shows whether
// new flows get through, not only whether established ones are slowed down.
func dns(args []string) {
	fs := flag.NewFlagSet("dns", flag.ExitOnError)
	rate := fs.Int("rate", 100, "new flows per second")
	dur := fs.Duration("dur", 10*time.Second, "how long to run")
	dst := fs.String("dst", "1.1.1.1:53", "DNS server")
	wait := fs.Duration("wait", 2*time.Second, "how long to wait for each answer")
	bind := fs.String("bind", "", "device to bind the sockets to, e.g. tun0")
	fs.Parse(args)
	lc := net.ListenConfig{Control: bindControl(*bind)}

	to, err := net.ResolveUDPAddr("udp4", *dst)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	// A query for example.com, type A, with the id patched per flow.
	query := []byte{0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0,
		7, 'e', 'x', 'a', 'm', 'p', 'l', 'e', 3, 'c', 'o', 'm', 0, 0, 1, 0, 1}

	var answered, failed atomic.Int64
	var wg sync.WaitGroup
	start := time.Now()
	deadline := start.Add(*dur)
	sent := 0
	ticker := time.NewTicker(time.Millisecond)
	defer ticker.Stop()
	for now := range ticker.C {
		if now.After(deadline) {
			break
		}
		for owed := int(float64(*rate) * now.Sub(start).Seconds()); sent < owed; sent++ {
			pc, err := lc.ListenPacket(context.Background(), "udp4", ":0")
			if err != nil {
				failed.Add(1)
				continue
			}
			q := append([]byte(nil), query...)
			q[0], q[1] = byte(sent>>8), byte(sent)
			if _, err := pc.WriteTo(q, to); err != nil {
				failed.Add(1)
				pc.Close()
				continue
			}
			wg.Add(1)
			go func() {
				defer wg.Done()
				defer pc.Close()
				buf := make([]byte, 512)
				pc.SetReadDeadline(time.Now().Add(*wait))
				if n, _, err := pc.ReadFrom(buf); err == nil && n >= 2 && buf[0] == q[0] && buf[1] == q[1] {
					answered.Add(1)
				}
			}()
		}
	}
	wg.Wait()
	fmt.Printf("dns: rate %d/s, %d queries, %d answered (%.1f%%), %d failed to send\n",
		*rate, sent, answered.Load(), 100*float64(answered.Load())/float64(max(sent, 1)), failed.Load())
}

func connect(args []string) {
	fs := flag.NewFlagSet("connect", flag.ExitOnError)
	n := fs.Int("n", 40, "sequential connects")
	dst := fs.String("dst", "1.1.1.1:443", "TCP destination")
	timeout := fs.Duration("timeout", 5*time.Second, "per-connect timeout")
	pause := fs.Duration("pause", 250*time.Millisecond, "pause between connects")
	bind := fs.String("bind", "", "device to bind the sockets to, e.g. tun0")
	fs.Parse(args)

	d := net.Dialer{Timeout: *timeout, Control: bindControl(*bind)}
	var times []time.Duration
	timeouts := 0
	for i := 0; i < *n; i++ {
		t0 := time.Now()
		c, err := d.Dial("tcp4", *dst)
		el := time.Since(t0)
		if err != nil {
			timeouts++
			fmt.Printf("connect %2d: failed after %v: %v\n", i, el.Round(time.Millisecond), err)
		} else {
			c.Close()
			times = append(times, el)
		}
		time.Sleep(*pause)
	}
	if len(times) == 0 {
		fmt.Printf("connect: 0 of %d succeeded\n", *n)
		return
	}
	sort.Slice(times, func(i, j int) bool { return times[i] < times[j] })
	pct := func(p float64) time.Duration { return times[int(p*float64(len(times)-1))] }
	fmt.Printf("connect: %d ok, %d failed; p50 %v, p90 %v, max %v\n", len(times), timeouts,
		pct(0.5).Round(time.Millisecond), pct(0.9).Round(time.Millisecond), times[len(times)-1].Round(time.Millisecond))
}
