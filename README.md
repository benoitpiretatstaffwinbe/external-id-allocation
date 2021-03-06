# external-id-allocation

Example of an external ID allocation package for NSO. It includes some example code to go out to an HTTP server to request an ID.

It consists of three actions and two kickers. Should be three kickers but today they cant explicitly run on delete so deletes are handled in a subscriber.

The three actions are

 * allocate
    * does the actual allocation and creates an entry in the response list
 * release
    * releases the allocation from the external system and also deletes the response entry for the service in question
 * re-deploy-service
    * re-deploys the service that requested the allocation

The two kickers are

 * external-id-allocator
    * executes the allocate action when a request is created
 * external-id-redeploy
    * exectues the re-deploy-service action when a response entry is created

The package needs python requests installed to do the external allocation, to install it with pip do
```
pip install requests
```

Example of how to use it manually (to illustrate the steps the package does). Make sure to have a service instance created already.

first create the two kickers
```
ncs_cli -u admin
unhide debug
configure
set external-id-allocation create-kickers
commit
show kickers
```

Before creating the request you have to decide if you want to use a random Integer as allocation or to test it with an actual external request

To test with an external request, set use-random to False i.e

```
set external-id-allocation use-random false
commit
```

There is a small example HTTP IPAM server in the test folder. The ipam-server.py script uses web.py so remember to install that first (with pip use)

In bash, not it ncs_cli :)
```
pip install web.py
```
Then start the server
```
cd packages/external-id-allocator/test
python ipam-server.py
```

Then create an allocation request (back in the ncs_cli of course). (The allocating service needs to be an existing instance)

```
set external-id-allocation request service-1 allocating-service /vlan[name=volvo]
commit
```

This will execute the allocation action and populate the response list

```
run show external-id-allocation
external-id-allocation create-kickers
NAME   ALLOCATING SERVICE   ERROR  ID
----------------------------------------
volvo  /vlan[name='volvo']  -      152

```

the allocate action can be manually executed if needed

```
request external-id-allocation request volvo allocate
```

to release the id the release action is executed
```
request external-id-allocation response volvo release
```
when the allocation is done the service should be re-deployed
```
request external-id-allocation response volvo re-deploy-service
```

And then putting the whole thing together with a service you let the service create the allocation request and then the kickers (and the subscriber) autmatically handles the rest.

Here is an example that populates the request, it will then create the switchport if the response has been created and also set allocated VLAN-id in trunk allowed vlans.

Service YANG

```
module: vlan
   +--rw vlan* [name]
      +--rw name                        string
      +--rw device?                     -> /ncs:devices/device/name
```

Service template

```XML
<config-template xmlns="http://tail-f.com/ns/config/1.0" servicepoint="vlan">
  <external-id-allocation xmlns="http://example.com/external-id-allocation">
    <request>
      <name>{/name}</name>
      <allocating-service xmlns:vlan="http://com/example/vlan">/vlan:vlan[vlan:name='{/name}']</allocating-service>
    </request>
  </external-id-allocation>
  <devices xmlns="http://tail-f.com/ns/ncs">
    <device>
      <name>{/device}</name>
      <config>
      <interface xmlns="urn:ios">
        <FastEthernet>
          <name>1/0</name>
          <switchport when="{../ext-id:external-id-allocation/ext-id:response[ext-id:name=/name]/ext-id:id}">
            <mode>
              <trunk/>
            </mode>
            <trunk>
              <allowed>
                <vlan>
                  <vlans>{../ext-id:external-id-allocation/ext-id:response[ext-id:name=/name]/ext-id:id}</vlans>
                </vlan>
              </allowed>
            </trunk>
          </switchport>
        </FastEthernet>
      </interface>
      </config>
    </device>
  </devices>
</config-template>
```

```
admin@ncs% set vlan volvo device c0
[ok][2017-03-20 18:14:55]

[edit]
admin@ncs% commit
Commit complete.
[ok][2017-03-20 18:14:59]

[edit]
admin@ncs%
System message at 2017-03-20 18:15:00...
Commit performed by admin via console using cli.
admin@ncs% show external-id-allocation
create-kickers;
request volvo {
    allocating-service /vlan[name='volvo'];
}
[ok][2017-03-20 18:15:03]

[edit]
admin@ncs% run show external-id-allocation
external-id-allocation create-kickers
NAME   ALLOCATING SERVICE   ERROR  ID
----------------------------------------
volvo  /vlan[name='volvo']  -      242

[ok][2017-03-20 18:15:10]

[edit]
admin@ncs% show devices device c0 config ios:interface FastEthernet | display service-meta-data
/* Refcount: 2 */
/* Backpointer: [ /vlan:vlan[vlan:name='volvo'] ] */
FastEthernet 1/0 {
    switchport {
        mode {
            /* Refcount: 1 */
            /* Backpointer: [ /vlan:vlan[vlan:name='volvo'] ] */
            trunk;
        }
        trunk {
            allowed {
                vlan {
                    vlans [ 156 ];
                }
            }
        }
    }
}
admin@ncs% delete vlan volvo
[ok][2017-03-20 18:15:14]

[edit]
admin@ncs% commit
Commit complete.
[ok][2017-03-20 18:15:15]

[edit]
admin@ncs% run show external-id-allocation
external-id-allocation create-kickers
[ok][2017-03-20 18:15:17]

[edit]
admin@ncs% show external-id-allocation
create-kickers;
[ok][2017-03-20 18:15:21]

[edit]
```

### Contact

Contact Hakan Niska <hniska@cisco.com> with any suggestions or comments. If you find any bugs please fix them and send me a pull request.
