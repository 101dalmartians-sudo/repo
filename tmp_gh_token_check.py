import os
keys = ['GITHUB_TOKEN', 'GH_TOKEN', 'GITHUB_API_TOKEN', 'TOKEN']
for k in keys:
    if k in os.environ:
        print(f'{k}={os.environ[k][:4] + "..." if os.environ[k] else "(empty)"}')
