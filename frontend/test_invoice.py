import sys, os, logging
logging.basicConfig(level=logging.WARNING, format='%(levelname)s %(name)s: %(message)s')

sys.path.insert(0, os.path.abspath('../backend'))

TEST_PDF = r'input\success\1777548322_Invoice_CloudMinds_NovaTech_2024_1_20260430_165522.pdf'
print('Running process_file on: ' + TEST_PDF)

from invoice_main import process_file
result = process_file(TEST_PDF, file_id=9999)

print()
print('=== RESULT ===')
print('status:', result.get('status'))
print('error: ', result.get('error'))
print('invoice_number:', result.get('invoice_number'))
structured = result.get('structured', {})
if structured:
    truthy = {k: v for k, v in structured.items() if v}
    print('structured truthy fields:', truthy)
else:
    print('structured: (empty)')
