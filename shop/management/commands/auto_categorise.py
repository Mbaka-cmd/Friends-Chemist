import re
from django.core.management.base import BaseCommand
from shop.models import Product
RULES = [
 ('Family Planning & Wellness', 'KISS LYDIA PREGNANCY MENOZIP'),
 ('Vitamins & Supplements', 'VITAMIN MULTIVIT SCOTTS SEVEN RANFERON IFAS ZINC CYPRO FERROLIC'),
 ('Cough & Cold', 'COUGH COFTA KALUMA FLUGONE TRIHIST TRICOHIST TRIDEX UPACOF NICOF TRIPACOFF AMBROX CADISTIN SALBUTAMOL'),
 ('Stomach & Digestive', 'ORS LOPERAMIDE GRIPE ESOMEPRAZOLE OMEPRAZOLE RELCER GASTRO ALLUCID'),
 ('Skin Care & Creams', 'CREAM OINT BALM DEEP GEL CLOTRIM CLOZOLE KETOCON CANAZOL PESS'),
 ('Diabetes', 'GLUCOMET NOGLUC MIXTARD INSULIN'),
 ('Heart & Blood Pressure', 'CARDITAN CARDINOL ENALAPRIL FUROSEMIDE HYDROCHLORO NIFEDIPINE AMLO VIDOL'),
 ('Pain Relief', 'PANADOL TRAMADOL DICLOFENAC BRUFEN IBU MELOXICAM ACECLOFENAC PCM MARA ACTION'),
 ('Antibiotics & Infections', 'AMOX CEF CIPRO AZITH ZITHROX METRONID DOXY FLUCLOX CLINDA ERYTHRO LEVOFLOX CEPHALEX GENTAMYCIN SPOTCLAV MINCLAV AMPICLOX NITROFURANTOIN TINIDAZOLE SECNIDAZOLE ALBENDAZOLE LEVAMISOLE GRISO FLUCONAZOLE NATOA DABORAL TAGERA'),
]
class Command(BaseCommand):
    help = 'Assign a starting category (by name keyword) to Chemist products with no category. Review in /admin/.'
    def handle(self, *a, **o):
        n = 0
        for p in Product.objects.filter(dept='chemist', category=''):
            name = p.name.upper()
            cat = next((c for c, kws in RULES if any(re.search(r'\b' + k, name) for k in kws.split())), 'Other medicines')
            p.category = cat; p.save(update_fields=['category']); n += 1
        self.stdout.write(f'{n} chemist products categorised (starting guess, please review).')