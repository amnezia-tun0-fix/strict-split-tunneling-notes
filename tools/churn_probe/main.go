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
//	churn_probe flows   -rate 1000 -dur 60s [-hold 2s] [-dst 192.0.2.1:9] [-dports N] [-bind tun0]
//	churn_probe connect -n 40 [-dst 1.1.1.1:443] [-timeout 5s] [-bind tun0]
//	churn_probe dns     -rate 1000 -dur 10s [-dst 1.1.1.1:53] [-wait 2s] [-bind tun0]
//	churn_probe stream  -rate 50 -dur 60s [-flows 1] [-burst 1] [-dst 1.1.1.1:53] [-wait 2s] [-bind tun0]
//
// stream keeps one UDP socket per flow for the whole run, so each flow is one
// long-lived 5-tuple, and sends DNS queries on it at a fixed rate; it reports
// how many were answered and where the unanswered ones fell. It is the long
// flow of an allowed app (QUIC, a call) whose verdict a cache keeps or loses.
// -burst N sends the queries N back to back, as QUIC does: a flow held while it
// is judged keeps only the first packets of a burst.
//
// flows opens a fresh unconnected UDP socket per flow and sends one datagram:
// every one is a new source port, so a new flow for the filter. By default the
// socket is closed at once, so its owner is often gone by the time it is looked
// up, the platform's most expensive answer. -hold keeps each socket open that
// long, so every owner resolves. The default destination is TEST-NET-1, which
// the server drops. -bind tun0 binds the sockets to the tunnel
// (SO_BINDTODEVICE), as an app outside the VPN would to bypass it. Source ports
// come from the kernel's ephemeral range, about 28000 on Android, so at 5000
// flows/s to one destination a 5-tuple repeats every few seconds and a cache of
// denied verdicts absorbs part of the flood; -dports spreads the destination
// port so that it does not.
package main

import (
	"context"
	"flag"
	"fmt"
	"math/rand/v2"
	"net"
	"os"
	"sort"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
)

func main() {
	// Termux runs binaries from its home through the system linker, which leaves
	// the binary's own path in os.Args[1]. Drop it so the mode comes first again.
	if len(os.Args) > 1 && strings.HasSuffix(os.Args[1], "churn_probe") {
		os.Args = append(os.Args[:1], os.Args[2:]...)
	}
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: churn_probe flows|connect|dns|stream [flags]")
		os.Exit(2)
	}
	switch os.Args[1] {
	case "flows":
		flows(os.Args[2:])
	case "connect":
		connect(os.Args[2:])
	case "dns":
		dns(os.Args[2:])
	case "stream":
		stream(os.Args[2:])
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
	dports := fs.Int("dports", 0, "spread flows over this many destination ports from -dst's port, at random")
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
			dst := net.Addr(to)
			if *dports > 1 {
				dst = &net.UDPAddr{IP: to.IP, Port: to.Port + rand.IntN(*dports)}
			}
			if sendOne(lc, dst, payload, *hold) {
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

// stream sends DNS queries on long-lived sockets, one per flow, and counts the
// answers: per flow, per second of the run, and the longest run of unanswered
// queries, which shows a flow held while it is judged again.
func stream(args []string) {
	fs := flag.NewFlagSet("stream", flag.ExitOnError)
	rate := fs.Int("rate", 50, "queries per second on each flow")
	dur := fs.Duration("dur", 60*time.Second, "how long to run")
	nflows := fs.Int("flows", 1, "long-lived flows, each its own socket")
	burst := fs.Int("burst", 1, "queries sent back to back")
	dst := fs.String("dst", "1.1.1.1:53", "DNS server")
	wait := fs.Duration("wait", 2*time.Second, "how long to wait for the last answers")
	bind := fs.String("bind", "", "device to bind the sockets to, e.g. tun0")
	fs.Parse(args)
	lc := net.ListenConfig{Control: bindControl(*bind)}

	to, err := net.ResolveUDPAddr("udp4", *dst)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	query := []byte{0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0,
		7, 'e', 'x', 'a', 'm', 'p', 'l', 'e', 3, 'c', 'o', 'm', 0, 0, 1, 0, 1}
	total := int(float64(*rate) * dur.Seconds())
	if total > 65536 {
		fmt.Fprintln(os.Stderr, "at most 65536 queries per flow: the id is 16 bits")
		os.Exit(2)
	}

	type flowRun struct {
		pc       net.PacketConn
		answered []atomic.Bool
		sentAt   []time.Duration
		sent     int
	}
	runs := make([]*flowRun, *nflows)
	for i := range runs {
		pc, err := lc.ListenPacket(context.Background(), "udp4", ":0")
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		runs[i] = &flowRun{pc: pc, answered: make([]atomic.Bool, total), sentAt: make([]time.Duration, total)}
	}
	var wg sync.WaitGroup
	for _, fr := range runs {
		wg.Add(1)
		go func(fr *flowRun) {
			defer wg.Done()
			buf := make([]byte, 512)
			for {
				n, _, err := fr.pc.ReadFrom(buf)
				if err != nil {
					return // closed at the end of the run
				}
				if id := int(buf[0])<<8 | int(buf[1]); n >= 2 && id < total {
					fr.answered[id].Store(true)
				}
			}
		}(fr)
	}

	start := time.Now()
	ticker := time.NewTicker(time.Millisecond)
	for now := range ticker.C {
		owed := min(int(float64(*rate)*now.Sub(start).Seconds()) / *burst * *burst, total)
		for _, fr := range runs {
			for ; fr.sent < owed; fr.sent++ {
				q := append([]byte(nil), query...)
				q[0], q[1] = byte(fr.sent>>8), byte(fr.sent)
				fr.sentAt[fr.sent] = now.Sub(start)
				fr.pc.WriteTo(q, to)
			}
		}
		if owed == total {
			break
		}
	}
	ticker.Stop()
	time.Sleep(*wait)
	for _, fr := range runs {
		fr.pc.Close()
	}
	wg.Wait()

	secs := int(dur.Seconds()) + 1
	lostPerSec := make([]int, secs)
	sent, answered, worstGap := 0, 0, time.Duration(0)
	for i, fr := range runs {
		ok, gapStart, gap := 0, -1, time.Duration(0)
		for q := 0; q < fr.sent; q++ {
			if fr.answered[q].Load() {
				ok++
				if gapStart >= 0 {
					gap = max(gap, fr.sentAt[q]-fr.sentAt[gapStart])
					gapStart = -1
				}
				continue
			}
			lostPerSec[int(fr.sentAt[q].Seconds())]++
			if gapStart < 0 {
				gapStart = q
			}
		}
		if gapStart >= 0 {
			gap = max(gap, fr.sentAt[fr.sent-1]-fr.sentAt[gapStart])
		}
		sent += fr.sent
		answered += ok
		worstGap = max(worstGap, gap)
		if *nflows <= 8 {
			fmt.Printf("flow %d: %d sent, %d answered, longest unanswered run %v\n", i, fr.sent, ok, gap.Round(time.Millisecond))
		}
	}
	var lossy []string
	for s, n := range lostPerSec {
		if n > 0 {
			lossy = append(lossy, fmt.Sprintf("%ds:%d", s, n))
		}
	}
	fmt.Printf("stream: %d flows x %d/s in bursts of %d for %v: %d sent, %d answered (%.2f%%), longest unanswered run %v\n",
		*nflows, *rate, *burst, *dur, sent, answered, 100*float64(answered)/float64(max(sent, 1)), worstGap.Round(time.Millisecond))
	fmt.Printf("stream: unanswered by second: %s\n", strings.Join(lossy, " "))
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
