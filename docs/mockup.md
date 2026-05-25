% ratgeber

Ratgeber - a DRBD/Linstor Configuration Advisor and Tutor
copyright (c) 2026 Always Up Networks. MIT License.

ratgeber>

---

ratgeber> I have a 3 tier web app - MySQL, Spring backend, Angular UI - running
in US-east AWS. I want active-standby HA with failover to US-west. I'd rather
use DNS switching than virtual IP.

Ratgeber: Ok, few questions before I can recommend anything useful:

- how many nodes per site?
- what RTO can you live with - meaning how many minutes of downtime is ok?
- how big is your MySQL data and what's the write rate - this matters for DRBD
  replication bandwidth
- are you cost sensitive or is performance the only thing that matters?
