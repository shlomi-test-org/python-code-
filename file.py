# flake8: noqa
a = "ASIAAQWSEDRFTGYHUJUJ"
output = subprocess.check_output(f"nslookup {domain}", shell=True, encoding='UTF-8')
