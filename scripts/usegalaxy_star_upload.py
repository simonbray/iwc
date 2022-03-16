import os
import logging

import requests

from bioblend import galaxy

DOCKSTORE_API_URL = "https://dockstore.org/api/ga4gh/trs/v2/tools"
DOCKSTORE_API_PARAMS = {
    'organization': 'iwc-workflows'
}

GALAXIES_TO_UPDATE_CREDENTIALS = [
    {'url': 'https://usegalaxy.org', 'key': os.getenv('IWC_KEY_USEGALAXY_ORG')},
    {'url': 'https://usegalaxy.eu', 'key': os.getenv('IWC_KEY_USEGALAXY_EU')},
    {'url': 'https://usegalaxy.org.au', 'key': os.getenv('IWC_KEY_USEGALAXY_ORG_AU')},
]

logging.getLogger().setLevel(logging.INFO)

# get all IWC workflows from Dockstore
dockstore_wfs = requests.get(DOCKSTORE_API_URL, params=DOCKSTORE_API_PARAMS).json()

# find the dockstore workflows which are not on Galaxy and install them
for galaxy_credentials in GALAXIES_TO_UPDATE_CREDENTIALS:
    gi = galaxy.GalaxyInstance(**galaxy_credentials)

    # get all current uploaded workflows
    galaxy_wfs = gi.workflows.get_workflows()
    galaxy_wf_trs_ids = [tag for wf in galaxy_wfs for tag in wf["tags"] if tag.startswith("trs:")]
    logging.info(f"Starting installation on {gi.base_url}...")

    for dockstore_wf in dockstore_wfs:
        for versioned_dockstore_wf in dockstore_wf["versions"]:
            if f"trs:{versioned_dockstore_wf['id']}" not in galaxy_wf_trs_ids:
                logging.info(f"Starting installation of {versioned_dockstore_wf['id']}")
                # workflow missing - let's install it
                trs_payload = {
                    'archive_source': 'trs_tool',
                    'trs_server': 'dockstore',
                    'trs_tool_id': versioned_dockstore_wf['id'].split(':')[0],
                    'trs_version_id': versioned_dockstore_wf['name']
                }
                trs_import = gi.make_post_request(f'{gi.url}/workflows', payload=trs_payload)

                if trs_import['status'] == 'success':
                    # Import successful -> all tools must be installed
                    # strip imported from the name, tag with the trs ID, and publish
                    imported_wf = gi.workflows.show_workflow(trs_import['id'])
                    gi.workflows.update_workflow(  # fix name and tag with trs ID
                        workflow_id=imported_wf['id'],
                        name=imported_wf['name'].rstrip(' (imported from uploaded file)'),
                        tags=imported_wf['tags'] + [f"trs:{versioned_dockstore_wf['id']}"],
                        published=True
                    )
                    logging.info(f"Workflow {versioned_dockstore_wf['id']} imported and published successfully.")
                else:
                    # Some tools are missing or there was another failure - log and delete the workflow
                    logging.error(f"Error importing {versioned_dockstore_wf['id']} with message {trs_import.get('message')}")
                    if trs_import.get('id'):
                        gi.workflows.delete_workflow(trs_import['id'])  # tidy up
