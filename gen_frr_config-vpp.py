import subprocess
import ipaddress
from jinja2 import Template
# Python 3.5 script
# subprocess module from stdlib improved in later versions

frr_config_template = '''frr version {{ frr_version }}
frr defaults traditional
hostname {{ router_hostname }}
log syslog informational
service integrated-vtysh-config
username iason nopassword
!
{% for interface in mpls_interfaces %}
interface {{ interface }}
 ip router openfabric 1
 ipv6 router openfabric 1
!
{% endfor %}
interface lo
 ip address {{ local_loopback }}/32
 ip router openfabric 1
 ipv6 address {{ local_loopback_ipv6 }}/128
 ipv6 router openfabric 1
 openfabric passive
!
{% if rr_router %}
router bgp 65010
 bgp router-id {{ local_loopback }}
 bgp log-neighbor-changes
 neighbor {{ neighbor1_loopback }} remote-as 65010
 neighbor {{ neighbor1_loopback }} update-source {{ local_loopback }}
 neighbor {{ neighbor2_loopback }} remote-as 65010
 neighbor {{ neighbor2_loopback }} update-source {{ local_loopback }}
 neighbor {{ neighbor3_loopback }} remote-as 65010
 neighbor {{ neighbor3_loopback }} update-source {{ local_loopback }}
 neighbor {{ neighbor4_loopback }} remote-as 65010
 neighbor {{ neighbor4_loopback }} update-source {{ local_loopback }}
 !
 address-family ipv4 unicast
  no neighbor {{ neighbor1_loopback }} activate
  no neighbor {{ neighbor2_loopback }} activate
  no neighbor {{ neighbor3_loopback }} activate
  no neighbor {{ neighbor4_loopback }} activate  
 exit-address-family
 !
 address-family l2vpn evpn
  neighbor {{ neighbor1_loopback }} activate
  neighbor {{ neighbor1_loopback }} route-reflector-client
  neighbor {{ neighbor2_loopback }} activate
  neighbor {{ neighbor2_loopback }} route-reflector-client
  neighbor {{ neighbor3_loopback }} activate
  neighbor {{ neighbor3_loopback }} route-reflector-client
  neighbor {{ neighbor4_loopback }} activate
  neighbor {{ neighbor4_loopback }} route-reflector-client
 exit-address-family
!
{% endif %}
{% if edge_router %}
router bgp 65010
 bgp router-id {{ local_loopback }}
 coalesce-time 1000
 neighbor {{ rr1_loopback }} remote-as 65010
 neighbor {{ rr1_loopback }} update-source {{ local_loopback }}
 neighbor {{ rr2_loopback }} remote-as 65010
 neighbor {{ rr2_loopback }} update-source {{ local_loopback }}
 !
 address-family ipv4 unicast
  no neighbor {{ rr1_loopback }} activate
  no neighbor {{ rr2_loopback }} activate
 exit-address-family
 !
 address-family l2vpn evpn
  neighbor {{ rr1_loopback }} activate
  neighbor {{ rr2_loopback }} activate
  advertise-all-vni
  advertise ipv4 unicast
 exit-address-family
!
router bgp 65000 vrf vrf_cust1
 address-family l2vpn evpn
  advertise ipv4 unicast
 exit-address-family
!
 address-family ipv4 unicast
  redistribute connected
 exit-address-family
!
router bgp 65000 vrf vrf_cust2
 address-family l2vpn evpn
  advertise ipv4 unicast
 exit-address-family
!
 address-family ipv4 unicast
  redistribute connected
 exit-address-family
 !
!
{% endif %}
router openfabric 1
 net {{ iso_net }}
!
bfd
!
line vty
!'''
mpls_int_map = {
    'S1': ['vpp0', 'vpp1', 'vpp2', 'vpp3'],
    'S2': ['vpp0', 'vpp1', 'vpp2', 'vpp3'],
    'L1': ['vpp0', 'vpp1', 'vpp2', 'vpp3'],
    'L2': ['vpp0', 'vpp1', 'vpp2', 'vpp3'],
    'L3': ['vpp0', 'vpp1', 'vpp2', 'vpp3'],
    'L4': ['vpp0', 'vpp1', 'vpp2', 'vpp3']
    }

def prepend_octet(octet):
    if len(octet) == 0 or len(octet) > 3:
        raise ValueError('incorrect octet {}'.format(octet))
    elif len(octet) == 3:
        return octet
    else:
        while len(octet) < 3:
            octet = '0' + octet
        return octet

frr_ver_run = subprocess.run(['/usr/lib/frr/zebra', '--version'],
                             stdout=subprocess.PIPE)
frr_ver = frr_ver_run.stdout.decode('utf-8')
frr_ver_start = frr_ver.index('version')
frr_ver_end = frr_ver.index('\n', frr_ver_start)
frr_version = frr_ver[frr_ver_start+8:frr_ver_end].strip()
with open('/etc/hostname', 'r', encoding='utf-8') as infile:
    router_hostname = infile.read().strip()

mpls_interfaces = mpls_int_map[router_hostname]
rr_router = True if 'S' in router_hostname else False
edge_router = True if 'L' in router_hostname else False

loopback_addr_run = subprocess.run(['ip', '-br', 'address', 'show', 'lo'],
                                   stdout=subprocess.PIPE)
loopback_addr_list = loopback_addr_run.stdout.decode(
    'utf-8').strip().split(' ')
for address in loopback_addr_list:
    if '/' not in address:
        continue
    try:
        slash = address.index('/')
        local_loopback = ipaddress.ip_address(address[:slash])
    except ValueError:
        continue
    if not local_loopback.is_loopback:
        break

loopback_addr_ipv6_run = subprocess.run(['ip', '-6', '-br', 'address', 'show', 'lo'],
                                   stdout=subprocess.PIPE)
loopback_addr_ipv6_list = loopback_addr_ipv6_run.stdout.decode(
    'utf-8').strip().split(' ')
for address in loopback_addr_ipv6_list:
    if '/' not in address:
        continue
    try:
        slash_ipv6 = address.index('/')
        local_loopback_ipv6 = ipaddress.ip_address(address[:slash_ipv6])
    except ValueError:
        continue
    if not local_loopback_ipv6.is_loopback:
        break

lo_octets = local_loopback.compressed.split('.')
neighbor_loopback = ipaddress.ip_address('127.0.0.27')
if edge_router:
    rr1_loopback = '172.16.250.1'
    rr2_loopback = '172.16.250.2'
if rr_router:
   if lo_octets[-1] == '1':
        neighbor1_last_octet = '101'        
        neighbor2_last_octet = '102'
        neighbor3_last_octet = '103'
        neighbor4_last_octet = '104'      
    elif lo_octets[-1] == '2':
        neighbor1_last_octet = '101'        
        neighbor2_last_octet = '102'
        neighbor3_last_octet = '103'
        neighbor4_last_octet = '104'     
    else:
        raise ValueError('unacceptable loopback address {}'.format(
            local_loopback.compressed))
    neighbor1_octets = lo_octets[:-1]
    neighbor1_octets.append(neighbor1_last_octet)
    neighbor1_loopback = ipaddress.ip_address('.'.join(neighbor1_octets))
    neighbor2_octets = lo_octets[:-1]
    neighbor2_octets.append(neighbor2_last_octet)
    neighbor2_loopback = ipaddress.ip_address('.'.join(neighbor2_octets))
    neighbor3_octets = lo_octets[:-1]
    neighbor3_octets.append(neighbor3_last_octet)
    neighbor3_loopback = ipaddress.ip_address('.'.join(neighbor3_octets))   
    neighbor4_octets = lo_octets[:-1]
    neighbor4_octets.append(neighbor4_last_octet)
    neighbor4_loopback = ipaddress.ip_address('.'.join(neighbor4_octets))
iso_net = [prepend_octet(x) for x in local_loopback.compressed.split('.')]
iso_net = ''.join(iso_net)
step = 0
for i in range(4, len(iso_net), 4):
    iso_net = iso_net[:i+step] + '.' + iso_net[i+step:]
    step += 1
iso_net = '49.0001.' + iso_net + '.00'
template = Template(frr_config_template)
rendered = template.render(frr_version=frr_version,
                           router_hostname=router_hostname,
                           mpls_interfaces=mpls_interfaces,
                           edge_router=edge_router,
                           local_loopback=local_loopback.compressed,
                           rr1_loopback=rr1_loopback.compressed,
                           rr2_loopback=rr2_loopback.compressed,
                           neighbor1_loopback=neighbor1_loopback.compressed,
                           neighbor2_loopback=neighbor2_loopback.compressed,
                           neighbor3_loopback=neighbor3_loopback.compressed,
                           neighbor4_loopback=neighbor4_loopback.compressed,
                           iso_net=iso_net,
                           sr_index=sr_index,
                           local_loopback_ipv6=local_loopback_ipv6
                           )
with open('frr_generated_config', 'w', encoding='utf-8') as config_file:
    for line in rendered.split('\n'):
        if line.strip():
            config_file.write(line+'\n')
