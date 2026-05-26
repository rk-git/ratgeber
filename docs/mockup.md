```
% ratgeber


Ratgeber - a DRBD/Linstor Configuration Advisor and Tutor
copyright (c) 2026 Always Up Networks. MIT License.

ratgeber>

---

ratgeber> (User): I have a 3 tier web app - MySQL, Spring backend, Angular UI - running
in US-east AWS. I want active-standby HA with failover to US-west. I'd rather
use DNS switching than virtual IP.

Ratgeber: Ok, few questions before I can recommend anything useful:

- how many nodes per site?
- what RTO can you live with - meaning how many minutes of downtime is ok?
- how big is your MySQL data and what's the write rate - this matters for DRBD
  replication bandwidth
- are you cost sensitive or is performance the only thing that matters?

---

ratgeber> (User): 3 nodes each site. RTO under 5 minutes. MySQL is about 2TB, maybe
50MB/s peak writes. We are a startup so cost matters but I cannot mess with
data integrity.

Ratgeber: One more thing - can you provision anything in a third AWS region?
Even a tiny instance? I need to ask because without a quorum witness, if the
heartbeat link between your two sites goes down, both sides think the other is
dead and both try to become primary. That is a split brain and it will corrupt
your MySQL data. It is non negotiable for a two site setup.

---

ratgeber> (User): Yes I can use EU-west for that.

Ratgeber: Good. Here is what I'd recommend given your constraints.

Topology - two sites, three nodes each, async DRBD replication between sites,
sync within each site. Small quorum witness in EU-west, a t3.micro is fine.


Heartbeat - Corosync handles this. 1 second heartbeat interval, node declared
dead after 3 misses. Critical - give Corosync its own dedicated VPC peering
link between sites, completely separate from your DRBD replication link. If you
share them and the link gets saturated during a heavy replication burst,
Corosync will miss heartbeats and trigger a false failover. Keep them separate.

On your DNS preference - you are right to avoid stretching L2 across regions,
that is a mess. Use Route 53 with health check aware failover routing. Set your
TTL to 30 seconds ahead of time. Configure your Spring connection pool to retry
on failover. Just be aware some clients cache DNS beyond TTL regardless - see
caveat at the end.

DRBD replication - async between sites to avoid cross region latency penalty,
sync within each site. At 50MB/s writes you need at least 400Mbps between
sites, I'd provision 1Gbps to give yourself headroom.

Cost - quorum witness t3.micro is about $8/month. VPC peering data transfer at
your write rate is roughly $90/month. Use GP3 EBS instead of IO2 for backing
storage, same performance cheaper. All in you are looking at $150-200/month
extra on top of what you have.

Here is roughly what it looks like:

US-East (Primary)            US-West (Standby)
[node1][node2][node3] <==DRBD async==> [node1][node2][node3]
      |                                        |
      |<====Corosync heartbeat (VPC)==========>|
      |                                        |
      +----------[Quorum Witness: EU-West]------+
                          |
                     [Route 53]
                     TTL 30 sec
                   health check

Failover sequence - heartbeat stops, 3 misses, US-west checks quorum witness,
witness confirms US-east is gone, Pacemaker promotes MySQL on US-west, triggers
Route 53 update, DNS propagates in 30-60 seconds, users land on US-west. You
should hit your 5 minute RTO comfortably, probably 2-3 minutes in practice.

Caveats - DNS caching on client side is not fully in your control. Some mobile
clients and browsers ignore TTL. If that bothers you, AWS Global Accelerator
solves it cleanly using Anycast but adds about $50/month. Your call.

Want me to go deeper on any of this - Linstor resource group config, Corosync
tuning, Route 53 health check setup? 

ratgeber> (User): Yes - how do I avoid the DNS caching problem without paying for
Global Accelerator?
---
Ratgeber: Fair enough, here are three approaches that cost nothing extra...

---
```
