#!/bin/sh
# OpenLand security toolkit installer (runs inside the built-in Debian 13 arm64 computer).
# Standard, publicly available tools from Debian's own archive, for systems you own or are
# explicitly authorized to test, CTFs and learning. Nothing is installed until you ask.
#
#   ol-security list                  show groups and what is installed
#   ol-security install [GROUP ...]   default: core web passwords traffic python
#   ol-security install metasploit    large (~1 GB+), only on explicit request
#   ol-security install burp          Burp Suite Community (Java), only on explicit request
#   ol-security remove GROUP
set -e
export DEBIAN_FRONTEND=noninteractive
G_core="nmap netcat-openbsd bind9-dnsutils whois masscan curl"
G_web="sqlmap nikto gobuster ffuf whatweb dirb"
G_passwords="john hashcat pocl-opencl-icd hydra"
G_traffic="tcpdump tshark"
G_python="python3-requests python3-scapy python3-impacket python3-pwntools"
G_metasploit="git ruby-full build-essential libpq-dev libpcap-dev libsqlite3-dev zlib1g-dev libyaml-dev"
G_burp="openjdk-21-jre-headless curl"
DEFAULT="core web passwords traffic python"
MSF_DIR=/opt/metasploit-framework
BURP_JAR=/opt/burp/burpsuite_community.jar

say() { echo "STEP $*"; }
pkgs() { eval echo "\$G_$1"; }
ensure_sources() {
  mkdir -p /var/cache/apt/archives/partial /var/lib/apt/lists/partial /var/lib/dpkg/updates /var/log/apt /tmp /run/lock; chmod 1777 /tmp
  echo "wireshark-common wireshark-common/install-setuid boolean false" | debconf-set-selections 2>/dev/null || true
  dpkg --configure -a >/dev/null 2>&1 || true
  f=/etc/apt/sources.list.d/openland-security.list
  [ -f "$f" ] || echo "deb https://deb.debian.org/debian trixie non-free" > "$f"   # nikto lives in non-free
  if [ ! -f /var/lib/apt/periodic/ol-sec-updated ] || [ -n "$(find /var/lib/apt/periodic/ol-sec-updated -mmin +720)" ]; then
    say "Updating package lists"; apt-get update -q; mkdir -p /var/lib/apt/periodic; touch /var/lib/apt/periodic/ol-sec-updated
  fi
}
installed() { dpkg-query -W -f='${Status}' "$1" 2>/dev/null | grep -q "ok installed"; }

case "${1:-list}" in
  list)
    for g in core web passwords traffic python metasploit burp; do
      miss=""; for p in $(pkgs $g); do installed $p || miss="$miss $p"; done
      st=installed; [ -n "$miss" ] && st="not installed"
      [ $g = metasploit ] && { [ -x $MSF_DIR/msfconsole ] || st="not installed"; }
      [ $g = burp ] && { [ -f $BURP_JAR ] || st="not installed"; }
      echo "$g: $st ($(pkgs $g))"
    done ;;
  install)
    shift; groups="${*:-$DEFAULT}"
    ensure_sources
    for g in $groups; do
      p=$(pkgs $g); [ -n "$p" ] || { echo "unknown group: $g" >&2; exit 2; }
      say "Installing $g: $p"
      apt-get install -y -q --no-install-recommends $p
      if [ $g = metasploit ] && [ ! -x $MSF_DIR/msfconsole ]; then
        say "Downloading Metasploit Framework (git, large)"
        git clone --depth 1 https://github.com/rapid7/metasploit-framework.git $MSF_DIR
        cd $MSF_DIR && gem install bundler --no-document && bundle config set --local without 'development test coverage' && bundle install -j"$(nproc)"
        ln -sf $MSF_DIR/msfconsole /usr/local/bin/msfconsole
      fi
      if [ $g = burp ] && [ ! -f $BURP_JAR ]; then
        say "Downloading Burp Suite Community"
        mkdir -p /opt/burp && curl -fL -o $BURP_JAR.part "https://portswigger.net/burp/releases/download?product=community&type=Jar" && mv $BURP_JAR.part $BURP_JAR
        printf '#!/bin/sh\nexec java -jar %s "$@"\n' $BURP_JAR > /usr/local/bin/burpsuite; chmod +x /usr/local/bin/burpsuite
      fi
    done
    apt-get clean
    echo "OK installed: $groups. Use only on systems you own or are authorized to test." ;;
  remove)
    shift; for g in "$@"; do apt-get remove -y -q $(pkgs $g) || true
      [ $g = metasploit ] && rm -rf $MSF_DIR /usr/local/bin/msfconsole; [ $g = burp ] && rm -rf /opt/burp /usr/local/bin/burpsuite; done
    apt-get autoremove -y -q; echo OK ;;
  *) sed -n '2,10p' "$0"; exit 2 ;;
esac
