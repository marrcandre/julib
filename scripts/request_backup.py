"""Request and await a private backup before production migration."""
import json
import os
import subprocess
import time
import uuid

repo=os.environ['BACKUP_REPOSITORY']
request_id='deploy-'+uuid.uuid4().hex
metadata=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}']))
if not metadata.get('private'):raise SystemExit('Backup repository must be private.')
subprocess.run(['gh','workflow','run','backup.yml','--repo',repo,'--ref','main','-f',f'request_id={request_id}'],check=True)
for attempt in range(60):
    runs=json.loads(subprocess.check_output(['gh','run','list','--repo',repo,'--workflow','backup.yml','--limit','20','--json','databaseId,displayTitle,status,conclusion']))
    match=next((run for run in runs if request_id in run['displayTitle']),None)
    if match and match['status']=='completed':
        if match['conclusion']!='success':raise SystemExit('Private backup failed. Deployment stopped.')
        print('Private backup completed successfully.');break
    time.sleep(5)
else:raise SystemExit('Timed out waiting for private backup. Deployment stopped.')
