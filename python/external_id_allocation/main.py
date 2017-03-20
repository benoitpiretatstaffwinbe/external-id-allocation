# -*- mode: python; python-indent: 4 -*-
import ncs
from ncs.application import Service
from ncs.dp import Action
import ncs.experimental
import _ncs
#random is just used for testing
import random

# ---------------
# ACTIONS EXAMPLE
# ---------------
class AllocateAction(Action):
    @Action.action
    def cb_action(self, uinfo, name, kp, input, output):
        self.log.info('action name: ', name)
        self.log.info('action kp: ', str(kp))
        #if the your actions take more than 240 seconds, increase the action_set_timeout
        #_ncs.dp.action_set_timeout(uinfo,240)
        #HERE YOU SHOULD DO YOUR EXTERNAL ALLOCATION
        with ncs.maapi.single_write_trans(uinfo.username, uinfo.context) as trans:
            allocation = ncs.maagic.get_node(trans, kp)
            allocation_name = allocation.name
            allocating_service = allocation.allocating_service
            response = allocation._parent._parent.response.create(allocation_name)
            response.id = random.randint(100, 1000)
            response.allocating_service = allocating_service
            #HERE YOU SHOULD DO YOUR EXTERNAL ALLOCATION
            trans.apply()
            self.log.info('action allocated id: ', str(response.id))

class ServiceCallbacks(Service):
    @Service.create
    def cb_create(self, tctx, root, service, proplist):
        self.log.info('Service create(service=', service._path, ')')

        vars = ncs.template.Variables()
        # vars.add('DUMMY', '127.0.0.1')
        template = ncs.template.Template(service)
        template.apply('external-id-allocation-template', vars)

# ------------------------------------------------
# SUBSCRIBER for deletes, only here until kickers can distingish between create/delete
# ------------------------------------------------
class DeleteSubscriber(ncs.experimental.Subscriber):
    def init(self):
        self.register('/ext-id:external-id-allocation/ext-id:request', priority=100)

    # Initate your local state
    def pre_iterate(self):
        return []

    # Iterate over the change set
    def iterate(self, keypath, op, oldval, newval, state):
        self.log.info('Delete Subscriber kp: ' + str(keypath))
        #2: 'MOP_DELETED',
        if op == 2:
            response_kp = str(keypath).replace('request', 'response')
            state.append(response_kp)
        return ncs.ITER_RECURSE

    # This will run in a separate thread to avoid a transaction deadlock
    def post_iterate(self, state):
        self.log.info('DeleteSubscriber: post_iterate, state=', state)
        response_kp = state[0]
        with ncs.maapi.single_read_trans('system', 'system') as trans:
            allocation = ncs.maagic.get_node(trans, response_kp)
            allocation.ext_id__release()
            self.log.info('Allocation released: ', response_kp)

    # determine if post_iterate() should run
    def should_post_iterate(self, state):
        return state != []


# ---------------------------------------------
# COMPONENT THREAD THAT WILL BE STARTED BY NCS.
# ---------------------------------------------
class Main(ncs.application.Application):
    def setup(self):
        # The application class sets up logging for us. It is accessible
        # through 'self.log' and is a ncs.log.Log instance.
        self.log.info('Main external-id-allocation RUNNING')

        # Service callbacks require a registration for a 'service point',
        # as specified in the corresponding data model.
        #
        self.register_service('external-id-allocation-servicepoint', ServiceCallbacks)

        # When using actions, this is how we register them:
        #
        self.register_action('external-id-allocation-action', AllocateAction)

        # Create your subscriber
        self.sub = DeleteSubscriber(app=self)
        self.sub.start()

    def teardown(self):
        # When the application is finished (which would happen if NCS went
        # down, packages were reloaded or some error occurred) this teardown
        # method will be called.

        self.sub.stop()

        self.log.info('Main FINISHED')