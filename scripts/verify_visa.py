import pyvisa
rm = pyvisa.ResourceManager()
print("  VISA lib:", rm.visalib)
rm.close()
