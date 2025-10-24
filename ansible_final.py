import subprocess

def showrun():
    # read https://www.datacamp.com/tutorial/python-subprocess to learn more about subprocess
    command = ['ansible-playbook', 'playbook_showrun.yml']
    result = subprocess.run(command, capture_output=True, text=True)
    result = result.stdout
    if 'ok=2' in result:
        return 'show_run_66070273_CSR1KV-Pod1-5.txt'
    else:
        return 'Error: Ansible'
