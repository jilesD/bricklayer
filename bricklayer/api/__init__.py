"""
    Wrappers for databricks_cli api and bring some sanity back with namespaces.
    Usage:
    ```
    import DBSApi
    # export notebook
    db = DBSApi()
    db.export_notebook(
        source_path='/Repos/deploy/dac-dbs-volume-projection-validation/02_validation_notebooks/90_run_vp_6',
        target_path= '/dbfs/mnt/external/tmp/90_run_vp_6'
    )
    # To save the current notebook to the runs folder
    db.export_current_notebook_run()
    ```
"""

import pathlib
import random
import datetime
import json

import requests
from databricks_cli.workspace.api import WorkspaceApi
from databricks_cli.jobs.api import JobsApi
from databricks_cli.sdk import ApiClient
from databricks_cli.clusters.api import ClusterApi
from databricks_cli.runs.api import RunsApi

from .. import get_notebook_context

class DBJobRun(object):

    def __init__(self, job, run_id, client):
        self.job = job
        self.run_id = run_id
        self._client = client
    
    @property
    def data(self):
        return RunsApi(self._client).get_run(self.run_id)

    @property
    def result_state(self):
        return self.data['state'].get('result_state')

    @property
    def life_cycle_state(self):
        return self.data['state'].get('life_cycle_state')

    @property
    def state_message(self):
        return self.data['state'].get('state_message')

    @property
    def run_page_url(self):
        return self.data['run_page_url']

    @property
    def attempt_number(self):
        return self.data['attempt_number']

    def get_run_output(self):
        data = RunsApi(self._client).get_run_output(self.run_id)
        return data.get('notebook_output')
    

    


class DBJob(object):
    def __init__(self, job_id, client):
        self.job_id = job_id
        self._client = client
        self.runs = []
    
    def run_now(self, jar_params=None, notebook_params=None, python_params=None,
                    spark_submit_params=None):
        """Run this job.
        :param jar_params: list of jars to be included
        :param notebook_params: map (dict) with the params to be passed to the job
        :param python_params: To pa passed to the notebook as if they were command-line parameters
        :param spark_submit_params: A list of parameters for jobs with spark submit task as command-line
                            parameters.
        """
        data = JobsApi(self._client).run_now(
            self.job_id,
            jar_params=jar_params,
            notebook_params=notebook_params,
            python_params=python_params,
            spark_submit_params=spark_submit_params
        )
        run = DBJobRun(self, data['run_id'], self._client)
        self.runs.append(run)
        return run


class DBSApi(object):

    def __init__(
        self,
        token=None,
        host=None,
        apiVersion='2.0',
    ):
        if token is None:
            token = get_notebook_context().get_api_token()
        
        if host is None:
            host = get_notebook_context().get_browser_host_name_url()

        self._client = ApiClient(
                            host=host,
                            apiVersion=apiVersion,
                            token=token
                            )

    def export_notebook(self, source_path, target_path, fmt='DBC', is_overwrite=False):
        "Export a notebook to a local file"
        (
            WorkspaceApi(self._client)
            .export_workspace(
                source_path,
                target_path,
                fmt,
                is_overwrite
            )
        )

    def import_notebook(self, source_path, target_path, language='PYTHON', fmt='DBC', is_overwrite=False):
        "Import a notebook from a local file"
        (
            WorkspaceApi(self._client)
            .import_workspace(
                source_path,
                target_path,
                language,
                fmt,
                is_overwrite
            )
        )

    def mkdir(self, dir_path):
        "Create a dir in the workspace"
        (
            WorkspaceApi(self._client)
            .mkdirs(
                dir_path
            )
        )

    def backup_notebook(self, source_path, target_path, tmp_dir='/dbfs/mnt/external/tmp/'):
        "Backup a notebook to another place in the workspace"
        tmp_name = f'backup_{random.randint(0,1000)}'
        intermediate_location = pathlib.Path(tmp_dir).joinpath(tmp_name)
        self.export_notebook(source_path, intermediate_location.as_posix())
        try:
            self.import_notebook(intermediate_location, target_path)
        finally:
            intermediate_location.unlink()

    def export_current_notebook_run(self, runs_dir='/Shared/runs/'):
        """Save the current notebook to a given location preserving
        the path and timestamp"""
        current_path = get_notebook_context().get_notebook_path()
        timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        target_path = (
                pathlib.Path(runs_dir)
                .joinpath(current_path[1:])
                .joinpath(timestamp)
        )
        try:
            self.backup_notebook(current_path, target_path.as_posix())
        except requests.exceptions.HTTPError as _e:
            error_code = _e.response.json()['error_code']
            if error_code == 'RESOURCE_DOES_NOT_EXIST':
                self.mkdir(target_path.parent.as_posix())
                self.backup_notebook(current_path, target_path.as_posix())
            else:
                raise
    
    def create_job(self, notebook_path, job_name=None, cluster_name=None,
            cluster_id=None, notifications_email=None):
        """Create a databricks job.
        :param notebook_path: The path of the notebook to be run in the job, can be relative
        :param job_name: Name of the job to be run, if missing it will use the notebook_path
        :param cluster_name: If provided the job will run in the cluster with this name
        :param cluster_id: If provided the job will run in the cluster with this id (should not
                            be provided at the same time with cluster_name)
        :param notifications_email: If provided notifications on success or failure on the job run
                            will be sent to this email address.
        """
        if cluster_name:
            assert cluster_id is None
            _cluster_id = ClusterApi(self._client).get_cluster_id_for_name(cluster_name)
        elif cluster_id:
            _cluster_id = cluster_id
        else:
            _cluster_id = get_notebook_context().get_notebook_cluster_id()

        if job_name:
            _job_name = job_name
        else:
            _job_name = notebook_path


        if not pathlib.Path(notebook_path).is_absolute():
            notebook_path = (
                pathlib
                .Path(get_notebook_context().get_notebook_path())
                .parent
                .joinpath(notebook_path)
                .as_posix()
            )
        
        _json = (
                    {
                    "name": _job_name,
                    "existing_cluster_id": _cluster_id,
                    "notebook_task": {
                        "notebook_path": notebook_path
                    },
                    "email_notifications": {
                        "on_success": [
                        notifications_email
                        ],
                        "on_failure": [
                        notifications_email
                        ]
                    }
                }
            )
        jobdata = JobsApi(self._client).create_job(_json)
        return DBJob(
            jobdata['job_id'],
            self._client
        )


