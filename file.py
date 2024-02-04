# flake8: noqa
a = "ASIAAQWSEDRFTGYHUJUJa"
output = subprocess.check_output(f"nslookup {domain}", shell=True, encoding='UTF-8')
output_2 = subprocess.check_output(f"nslookup {domain}", shell=True, encoding='UTF-8')
