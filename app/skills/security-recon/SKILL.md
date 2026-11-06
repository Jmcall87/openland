---
name: security-recon
description: Recon and enumeration for authorized security testing, CTFs and learning, using standard tools in the built-in Linux computer (nmap, sqlmap, nikto, gobuster, ffuf, whatweb, dig, tcpdump, john, hashcat). Use when the user asks to scan, enumerate or assess a host, web app or network they own or are authorized to test.
---

# Security recon (authorized testing only)

## Scope comes first
- Only test systems the user **owns** or has **explicit written permission** to test (a pentest engagement, a bug-bounty program's in-scope assets, a CTF, or a lab such as their own VM, DVWA, Juice Shop or Metasploitable).
- Before the first scan, confirm the target and the authorization in one sentence. If the user can't say they're authorized, or the target looks like someone else's system (a company, a government site, a random IP), don't scan it. Offer a legal lab target instead.
- Bug-bounty: follow the program's scope and rate limits. No denial of service, no social engineering, no touching other users' data.
- Never use these tools to get into accounts or systems the user doesn't control, steal credentials, or deploy malware.

## Setup
Tools install on demand. Run `ol-security list` to see what's there, and `ol-security install` to add the default set (core, web, passwords, traffic, python). Metasploit (`ol-security install metasploit`) and Burp Suite Community (`ol-security install burp`) are large, so install them only when the user asks for them.

## Workflow
1. **Passive first.** Run `whois <domain>` and `dig +short <domain> A AAAA MX NS TXT`. Check the program's scope file.
2. **Host discovery** (your own LAN or lab only): `nmap -sn 192.168.56.0/24`
3. **Ports and services:** `nmap -sV -sC -T3 --top-ports 1000 -oA ~/scans/target <host>`. Add `-p-` for all ports, given time and permission. Use masscan only on your own ranges and with `--rate 1000` or lower.
4. **Web fingerprint:** `whatweb -a 1 https://target`, then `nikto -h https://target -Tuning 123b -maxtime 15m`
5. **Content discovery:** `gobuster dir -u https://target -w /usr/share/dirb/wordlists/common.txt -t 10`, or `ffuf -u https://target/FUZZ -w wordlist -rate 20 -mc 200,204,301,302,403`
6. **SQL injection check** (in scope only): `sqlmap -u "https://target/item?id=1" --batch --level 1 --risk 1`. Don't use `--dump` on real data unless the engagement explicitly allows it. Prefer `--banner` / `--current-db` as proof.
7. **Traffic** (your own interfaces): `tcpdump -i any -w ~/scans/cap.pcap`, then `tshark -r ~/scans/cap.pcap -q -z conv,ip`
8. **Hashes** (from your own lab or CTF): `john --wordlist=/usr/share/john/password.lst hashes.txt`, or `hashcat -m <mode> -a 0 hashes.txt wordlist` (CPU, so slow on a phone).
9. **Python:** use `requests`, `scapy`, `impacket` and `pwntools` for CTF scripts and lab protocol work.

## Reporting
Save outputs under `~/scans/`. Summarize each finding with: target, evidence (command plus trimmed output), severity, and remediation. Tell the user what was **not** tested.

## Phone notes
The computer runs without root networking, so raw-socket scans (`nmap -sS`, masscan, ARP discovery) may be limited. Prefer `nmap -sT` (connect scan). Keep thread counts low to save battery and heat.
