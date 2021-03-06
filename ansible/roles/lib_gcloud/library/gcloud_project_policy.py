#!/usr/bin/env python
#     ___ ___ _  _ ___ ___    _ _____ ___ ___
#    / __| __| \| | __| _ \  /_\_   _| __|   \
#   | (_ | _|| .` | _||   / / _ \| | | _|| |) |
#    \___|___|_|\_|___|_|_\/_/_\_\_|_|___|___/_ _____
#   |   \ / _ \  | \| |/ _ \_   _| | __|   \_ _|_   _|
#   | |) | (_) | | .` | (_) || |   | _|| |) | |  | |
#   |___/ \___/  |_|\_|\___/ |_|   |___|___/___| |_|

'''
   GcloudCLI class that wraps the oc commands in a subprocess
'''

import atexit
import json
import os
import random
# Not all genearated modules use this.
# pylint: disable=unused-import
import re
import shutil
import string
import subprocess
import tempfile
import yaml
# Not all genearated modules use this.
# pylint: disable=unused-import
import copy
# pylint: disable=import-error
from apiclient.discovery import build
# pylint: disable=import-error
from oauth2client.client import GoogleCredentials



class GcloudCLIError(Exception):
    '''Exception class for openshiftcli'''
    pass

# pylint: disable=too-few-public-methods
class GcloudCLI(object):
    ''' Class to wrap the command line tools '''
    def __init__(self, credentials=None, verbose=False):
        ''' Constructor for OpenshiftCLI '''
        self.scope = None

        if not credentials:
            self.credentials = GoogleCredentials.get_application_default()
        else:
            tmp = tempfile.NamedTemporaryFile()
            tmp.write(json.dumps(credentials))
            tmp.seek(0)
            self.credentials = GoogleCredentials.from_stream(tmp.name)
            tmp.close()

        self.scope = build('compute', 'beta', credentials=self.credentials)

        self.verbose = verbose

    def _create_image(self, image_name, image_info):
        '''create an image name'''
        cmd = ['compute', 'images', 'create', image_name]
        for key, val in image_info.items():
            if val:
                cmd.extend(['--%s' % key, val])

        return self.gcloud_cmd(cmd, output=True, output_type='raw')

    def _delete_image(self, image_name):
        '''delete image by name '''
        cmd = ['compute', 'images', 'delete', image_name]
        if image_name:
            cmd.extend(['describe', image_name])
        else:
            cmd.append('list')

        cmd.append('-q')

        return self.gcloud_cmd(cmd, output=True, output_type='raw')

    def _list_images(self, image_name=None):
        '''list images.
           if name is supplied perform a describe and return
        '''
        cmd = ['compute', 'images']
        if image_name:
            cmd.extend(['describe', image_name])
        else:
            cmd.append('list')

        return self.gcloud_cmd(cmd, output=True, output_type='raw')

    def _list_deployments(self, simple=True):
        '''list deployments by name '''
        cmd = ['deployment-manager', 'deployments', 'list']
        if simple:
            cmd.append('--simple-list')
        return self.gcloud_cmd(cmd, output=True, output_type='raw')

    def _delete_deployment(self, dname):
        '''list deployments by name '''
        cmd = ['deployment-manager', 'deployments', 'delete', dname, '-q']
        return self.gcloud_cmd(cmd, output=True, output_type='raw')

    def _create_deployment(self, dname, config=None, opts=None):
        ''' create a deployment'''
        cmd = ['deployment-manager', 'deployments', 'create', dname]
        if config:
            if isinstance(config, dict):
                config = Utils.create_file(dname, config)

            if isinstance(config, str) and os.path.exists(config):
                cmd.extend(['--config=%s' % config])

        if opts:
            for key, val in opts.items():
                cmd.append('--%s=%s' % (key, val))

        return self.gcloud_cmd(cmd, output=True, output_type='raw')

    def _update_deployment(self, dname, config=None, opts=None):
        ''' create a deployment'''
        cmd = ['deployment-manager', 'deployments', 'update', dname]
        if config:
            if isinstance(config, dict):
                config = Utils.create_file(dname, config)

            if isinstance(config, str) and os.path.exists(config):
                cmd.extend(['--config=%s' % config])

        if opts:
            for key, val in opts.items():
                cmd.append('--%s=%s' % (key, val))

        return self.gcloud_cmd(cmd, output=True, output_type='raw')

    def _list_manifests(self, deployment, mname=None):
        ''' list manifests
            if a name is specified then perform a describe
        '''
        cmd = ['deployment-manager', 'manifests', '--deployment', deployment]
        if mname:
            cmd.extend(['describe', mname])
        else:
            cmd.append('list')

        cmd.extend(['--format', 'json'])

        return self.gcloud_cmd(cmd, output=True, output_type='json')

    def _delete_address(self, aname):
        ''' list addresses
            if a name is specified then perform a describe
        '''
        cmd = ['compute', 'addresses', 'delete', aname, '-q']

        return self.gcloud_cmd(cmd, output=True, output_type='raw')

    def _list_addresses(self, aname=None):
        ''' list addresses
            if a name is specified then perform a describe
        '''
        cmd = ['compute', 'addresses']
        if aname:
            cmd.extend(['describe', aname])
        else:
            cmd.append('list')

        return self.gcloud_cmd(cmd, output=True, output_type='raw')

    def _create_address(self, address_name, address_info, address=None, isglobal=False):
        ''' create a deployment'''
        cmd = ['compute', 'addresses', 'create', address_name]

        if address:
            cmd.append(address)

        if isglobal:
            cmd.append('--global')

        for key, val in address_info.items():
            if val:
                cmd.extend(['--%s' % key, val])

        return self.gcloud_cmd(cmd, output=True, output_type='raw')

    def _list_metadata(self):
        '''create metadata'''
        cmd = ['compute', 'project-info', 'describe']

        return self.gcloud_cmd(cmd, output=True, output_type='raw')

    def _delete_metadata(self, keys, remove_all=False):
        '''create metadata'''
        cmd = ['compute', 'project-info', 'remove-metadata']

        if remove_all:
            cmd.append('--all')

        else:
            cmd.append('--keys')
            cmd.append(','.join(keys))

        cmd.append('-q')

        return self.gcloud_cmd(cmd, output=True, output_type='raw')

    def _create_metadata(self, metadata=None, metadata_from_file=None):
        '''create metadata'''
        cmd = ['compute', 'project-info', 'add-metadata']

        data = None

        if metadata_from_file:
            cmd.append('--metadata-from-file')
            data = metadata_from_file
        else:
            cmd.append('--metadata')
            data = metadata

        cmd.append(','.join(['%s=%s' % (key, val) for key, val in data.items()]))

        return self.gcloud_cmd(cmd, output=True, output_type='raw')

    def _list_service_accounts(self, sa_name=None):
        '''return service accounts '''
        cmd = ['iam', 'service-accounts']
        if sa_name:
            cmd.extend(['describe', sa_name])
        else:
            cmd.append('list')

        cmd.extend(['--format', 'json'])

        return self.gcloud_cmd(cmd, output=True, output_type='json')

    def _delete_service_account(self, sa_name):
        '''delete service account '''
        cmd = ['iam', 'service-accounts', 'delete', sa_name, '-q']

        cmd.extend(['--format', 'json'])

        return self.gcloud_cmd(cmd, output=True, output_type='json')

    def _create_service_account(self, sa_name, display_name=None):
        '''create service account '''
        cmd = ['iam', 'service-accounts', 'create', sa_name]
        if display_name:
            cmd.extend(['--display-name', display_name])

        cmd.extend(['--format', 'json'])

        return self.gcloud_cmd(cmd, output=True, output_type='json')

    def _update_service_account(self, sa_name, display_name=None):
        '''update service account '''
        cmd = ['iam', 'service-accounts', 'update', sa_name]
        if display_name:
            cmd.extend(['--display-name', display_name])

        cmd.extend(['--format', 'json'])

        return self.gcloud_cmd(cmd, output=True, output_type='json')

    def _delete_service_account_key(self, sa_name, key_id):
        '''delete service account key'''
        cmd = ['iam', 'service-accounts', 'keys', 'delete', key_id, '--iam-account', sa_name, '-q']

        return self.gcloud_cmd(cmd, output=True, output_type='raw')

    def _list_service_account_keys(self, sa_name):
        '''return service account keys '''
        cmd = ['iam', 'service-accounts', 'keys', 'list', '--iam-account', sa_name]

        cmd.extend(['--format', 'json'])

        return self.gcloud_cmd(cmd, output=True, output_type='json')

    def _create_service_account_key(self, sa_name, outputfile, key_format='p12'):
        '''create service account key '''
        # Ensure we remove the key file
        atexit.register(Utils.cleanup, [outputfile])

        cmd = ['iam', 'service-accounts', 'keys', 'create', outputfile,
               '--iam-account', sa_name, '--key-file-type', key_format]

        return self.gcloud_cmd(cmd, output=True, output_type='raw')

    def _list_project_policy(self, project):
        '''create service account key '''
        cmd = ['projects', 'get-iam-policy', project]

        cmd.extend(['--format', 'json'])

        return self.gcloud_cmd(cmd, output=True, output_type='json')

    def _add_project_policy(self, project, member, role):
        '''create service account key '''
        cmd = ['projects', 'add-iam-policy-binding', project, '--member', member, '--role', role]

        cmd.extend(['--format', 'json'])

        return self.gcloud_cmd(cmd, output=True, output_type='json')

    def _remove_project_policy(self, project, member, role):
        '''create service account key '''
        cmd = ['projects', 'remove-iam-policy-binding', project, '--member', member, '--role', role]

        cmd.extend(['--format', 'json'])

        return self.gcloud_cmd(cmd, output=True, output_type='json')

    def _set_project_policy(self, project, policy_path):
        '''create service account key '''
        cmd = ['projects', 'set-iam-policy', project, policy_path]

        cmd.extend(['--format', 'json'])

        return self.gcloud_cmd(cmd, output=True, output_type='json')

    def _list_zones(self):
        ''' list zones '''
        cmd = ['compute', 'zones', 'list']

        cmd.extend(['--format', 'json'])

        return self.gcloud_cmd(cmd, output=True, output_type='json')

    def _config_set(self, config_param, config_value, config_section):
        ''' set config params with gcloud config set '''
        param = config_section + '/' + config_param
        cmd = ['config', 'set', param, config_value]

        cmd.extend(['--format', 'json'])

        return self.gcloud_cmd(cmd, output=True, output_type='json')

    def _list_config(self):
        '''return config '''
        cmd = ['config', 'list']

        cmd.extend(['--format', 'json'])

        return self.gcloud_cmd(cmd, output=True, output_type='json')

    def list_disks(self, zone=None, disk_name=None):
        '''return a list of disk objects in this project and zone'''
        cmd = ['beta', 'compute', 'disks']
        if disk_name and zone:
            cmd.extend(['describe', disk_name, '--zone', zone])
        else:
            cmd.append('list')

        cmd.extend(['--format', 'json'])

        return self.gcloud_cmd(cmd, output=True, output_type='json')

    # disabling too-many-arguments as these are all required for the disk labels
    # pylint: disable=too-many-arguments
    def _set_disk_labels(self, project, zone, dname, labels, finger_print):
        '''create service account key '''
        if labels == None:
            labels = {}

        self.scope = build('compute', 'beta', credentials=self.credentials)
        body = {'labels': labels, 'labelFingerprint': finger_print}
        result = self.scope.disks().setLabels(project=project,
                                              zone=zone,
                                              resource=dname,
                                              body=body,
                                             ).execute()

        return result

    def gcloud_cmd(self, cmd, output=False, output_type='json'):
        '''Base command for gcloud '''
        cmds = ['/usr/bin/gcloud']

        cmds.extend(cmd)

        rval = {}
        results = ''
        err = None

        if self.verbose:
            print ' '.join(cmds)

        proc = subprocess.Popen(cmds,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                env={})

        stdout, stderr = proc.communicate()
        rval = {"returncode": proc.returncode,
                "results": results,
                "cmd": ' '.join(cmds),
               }

        if proc.returncode == 0:
            if output:
                if output_type == 'json':
                    try:
                        rval['results'] = json.loads(stdout)
                    except ValueError as err:
                        if "No JSON object could be decoded" in err.message:
                            err = err.message
                elif output_type == 'raw':
                    rval['results'] = stdout

            if self.verbose:
                print stdout
                print stderr

            if err:
                rval.update({"err": err,
                             "stderr": stderr,
                             "stdout": stdout,
                             "cmd": cmds
                            })

        else:
            rval.update({"stderr": stderr,
                         "stdout": stdout,
                         "results": {},
                        })

        return rval

################################################################################
# utilities and helpers for generation
################################################################################
class Utils(object):
    ''' utilities for openshiftcli modules '''

    COMPUTE_URL_BASE = 'https://www.googleapis.com/compute/v1/'

    @staticmethod
    def create_file(rname, data, ftype='yaml'):
        ''' create a file in tmp with name and contents'''
        path = os.path.join('/tmp', rname)
        with open(path, 'w') as fds:
            if ftype == 'yaml':
                fds.write(yaml.safe_dump(data, default_flow_style=False))

            elif ftype == 'json':
                fds.write(json.dumps(data))
            else:
                fds.write(data)

        # Register cleanup when module is done
        atexit.register(Utils.cleanup, [path])
        return path

    @staticmethod
    def global_compute_url(project, collection, rname):
        '''build the global compute url for a resource'''
        return ''.join([Utils.COMPUTE_URL_BASE, 'projects/', project, '/global/', collection, '/', rname])

    @staticmethod
    def zonal_compute_url(project, zone, collection, rname):
        '''build the zone compute url for a resource'''
        return ''.join([Utils.COMPUTE_URL_BASE, 'projects/', project, '/zones/', zone, '/', collection, '/', rname])

    @staticmethod
    def generate_random_name(size):
        '''generate a random string of lowercase and digits the length of size'''
        return ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(size))


    @staticmethod
    def cleanup(files):
        '''Clean up on exit '''
        for sfile in files:
            if os.path.exists(sfile):
                if os.path.isdir(sfile):
                    shutil.rmtree(sfile)
                elif os.path.isfile(sfile):
                    os.remove(sfile)


# pylint: disable=too-many-instance-attributes
class GcloudProjectPolicy(GcloudCLI):
    ''' Class to wrap the gcloud compute iam service-accounts command'''

    # pylint allows 5
    # pylint: disable=too-many-arguments
    def __init__(self,
                 project,
                 role=None,
                 member=None,
                 member_type='serviceAccount',
                 verbose=False):
        ''' Constructor for gcloud resource '''
        super(GcloudProjectPolicy, self).__init__()
        self._project = project
        self._role = role
        self._member = '%s:%s' % (member_type, member)
        self._exist_policy = None
        self._policy_data = None
        self._policy_path = None
        self.verbose = verbose

    @property
    def existing_policy(self):
        '''existing project policy'''
        if self._exist_policy == None:
            results = self.list_project_policy()
            self._exist_policy = results['results']

        return self._exist_policy

    @property
    def project(self):
        '''property for project'''
        return self._project

    @property
    def member(self):
        '''property for member'''
        return self._member

    @property
    def role(self):
        '''property for role '''
        return self._role

    @property
    def policy_path(self):
        '''property for policy path'''
        return self._policy_path

    @policy_path.setter
    def policy_path(self, value):
        '''property for policy path'''
        self._policy_path = value

    @property
    def policy_data(self):
        '''property for policy data'''
        return self._policy_data

    @policy_data.setter
    def policy_data(self, value):
        '''property for policy data'''
        self._policy_data = value

    def list_project_policy(self):
        '''return project policy'''
        return self._list_project_policy(self.project)

    def remove_project_policy(self):
        ''' remove a member from a role in a project'''
        return self._remove_project_policy(self.project, self.member, self.role)

    def add_project_policy(self):
        '''create an service account key'''
        return self._add_project_policy(self.project, self.member, self.role)

    def set_project_policy(self, policy_data=None, policy_path=None):
        '''set a project policy '''
        # set the policy data and policy path
        self.convert_to_file(policy_data, policy_path)

        return self._set_project_policy(self.project, self.policy_path)

    def exists(self):
        '''check whether a member is in a project policy'''
        for policy in self.existing_policy['bindings']:
            if policy['role'] == self.role:
                return self.member in policy['members']

        return False

    def needs_update(self, policy_data=None, policy_path=None):
        '''compare results with incoming policy'''
        # set the policy data and policy path
        self.convert_to_file(policy_data, policy_path)

        for policy in self.policy_data['bindings']:
            for exist_policy in self.existing_policy['bindings']:
                if policy['role'] == exist_policy['role']:
                    if policy['members'] != exist_policy['members']:
                        return True
                    break
            else:
                # Did not find the role
                return True

        return False

    def convert_to_file(self, policy_data=None, policy_path=None):
        '''convert the policy data into a dict and ensure we have a file'''
        if policy_data:
            self.policy_data = policy_data
            self.policy_path = Utils.create_file('policy', policy_data, 'json')

        elif policy_path:
            self.policy_data = json.load(open(policy_path))
            self.policy_path = policy_path
# vim: expandtab:tabstop=4:shiftwidth=4

#pylint: disable=too-many-branches
def main():
    ''' ansible module for gcloud project policy'''
    module = AnsibleModule(
        argument_spec=dict(
            # credentials
            state=dict(default='present', type='str', choices=['present', 'absent', 'list']),
            project=dict(required=True, type='str'),
            member=dict(default=None, type='str'),
            member_type=dict(type='str', choices=['serviceAccount', 'user']),
            role=dict(default=None, type='str'),
            policy_data=dict(default=None, type='dict'),
            policy_path=dict(default=None, type='str'),
        ),
        supports_check_mode=True,
        mutually_exclusive=[['policy_path', 'policy_data']],
    )

    gcloud = GcloudProjectPolicy(module.params['project'],
                                 module.params['role'],
                                 module.params['member'],
                                 module.params['member_type'])

    state = module.params['state']

    api_rval = gcloud.list_project_policy()

    #####
    # Get
    #####
    if state == 'list':

        if api_rval['returncode'] != 0:
            module.fail_json(msg=api_rval, state="list")

        module.exit_json(changed=False, results=api_rval['results'], state="list")

    ########
    # Delete
    ########
    if state == 'absent':
        if gcloud.exists():

            if module.check_mode:
                module.exit_json(changed=False, msg='Would have performed a delete.')

            api_rval = gcloud.remove_project_policy()

            if api_rval['returncode'] != 0:
                module.fail_json(msg=api_rval)

            module.exit_json(changed=True, results=api_rval, state="absent")

        module.exit_json(changed=False, results=api_rval, state="absent")

    if state == 'present':
        ########
        # Create
        ########
        if module.params['policy_data'] or module.params['policy_path']:


            if gcloud.needs_update(module.params['policy_data'], module.params['policy_path']):
                # perform set
                if module.check_mode:
                    module.exit_json(changed=False, msg='Would have performed a set policy.')

                api_rval = gcloud.set_project_policy(module.params['policy_data'], module.params['policy_path'])

                if api_rval['returncode'] != 0:
                    module.fail_json(msg=api_rval)

                module.exit_json(changed=True, results=api_rval, state="present")

            module.exit_json(changed=False, results=api_rval, state="present")


        if not gcloud.exists():
            if module.check_mode:
                module.exit_json(changed=False, msg='Would have performed a create.')

            api_rval = gcloud.add_project_policy()

            if api_rval['returncode'] != 0:
                module.fail_json(msg=api_rval)

            module.exit_json(changed=True, results=api_rval, state="present")

        module.exit_json(changed=False, results=api_rval, state="present")

    module.exit_json(failed=True,
                     changed=False,
                     results='Unknown state passed. %s' % state,
                     state="unknown")


# pylint: disable=redefined-builtin, unused-wildcard-import, wildcard-import, locally-disabled
# import module snippets.  This are required
from ansible.module_utils.basic import *

main()
