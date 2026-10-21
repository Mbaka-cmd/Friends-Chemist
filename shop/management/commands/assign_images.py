import re, shutil
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand
from shop.models import Product

MAP = [
    ("1L Kausha 480 sl.jpg", ["Kaushia"]),
    ("1L Tingatinga 380 SC.jpg", ["Tingatinga"]),
    ("2,4 D-MAX 72.png", ["DMAX"]),
    ("acenex.jpg", ["Acenex"]),
    ("albendazol 20ml.jpg", ["Abedazole"]),
    ("Animatic calcyum.jpg", ["Animatic CAL"]),
    ("animatic cattle mix.jpg", ["Animatic cattle mix"]),
    ("b-safi 100ml.png", ["B-Safi"]),
    ("betmix.jpg", ["Beemix"]),
    ("BOOSTER.png", ["Booster"]),
    ("ckl dcp.jpg", ["CKL DCP"]),
    ("copper sulphate.jpg", ["Ngombemix DCP copper sulphate"]),
    ("diamond v 1000.jpg", ["Diamond V 1000"]),
    ("diamond v.jpg", ["Diamond V 100"]),
    ("EPSO, SALT 500G.jpg", ["Epsom salt", "Epsom", "Epsom soluble"]),
    ("Escort-19-EC.jpg", ["Escort"]),
    ("extra megalix.jpg", ["Extra Magalicks"]),
    ("extra milk lick.jpg", ["Extra meal lick"]),
    ("fastgrow flower.jpg", ["Fastgrow Flower"]),
    ("Fastgrow top.jpg", ["Fastgrow Top"]),
    ("fastgrow veg.jpg", ["Fastgrow Veg"]),
    ("FORCE 1  SUPER.jpg", ["Force One Super"]),
    ("FORCE 1 PLUS.jpg", ["Force One Plus"]),
    ("Kolopa 300 OD 1 Litre.jpg", ["Kolopa"]),
    ("Kraal salt.jpg", ["Kraal salt"]),
    ("kupa.repacow.jpg", ["Kupa/repacow"]),
    ("Macklic dry cow 5kg.jpg", ["Macklick Dry cow", "Maclick Dry"]),
    ("Maclik-BEEF 5kg.png", ["Macklick Beef", "Maclick Beef"]),
    ("xkl xtra brick salk.png", ["CKL block"]),
    ("macklic mineral brick.jpg", ["Maclick Plus", "Maclick Super"]),
    ("magicpig 1kg.jpg", ["Magical pig"]),
    ("malava chap.jpg", ["Malava chapp"]),
    ("maziwa chapchap 1kg.jpg", ["Mawua chapp"]),
    ("mastite.jpg", ["Masitite ketup"]),
    ("milk replacer.jpg", ["Milk replacer", "Milk replacer cow"]),
    ("Mr Bean.jpg", ["Mr Bean"]),
    ("MULTER CURE.jpg", ["Multer cure"]),
    ("multi vitamin suppliment cow.jpg", ["Multivitamin supplement cow"]),
    ("ng'ombe mix dcp.jpg", ["Ngombemix DCP"]),
    ("ng'ombe mix maziwa mengi.jpg", ["Ngombemix maize"]),
    ("ng'ombe mix ngoma.jpg", ["Ngombemix Ngoma"]),
    ("ng'ombe mix ndama.jpg", ["Ngombemix mineral lick", "Ngombemix mineral block"]),
    ("NILZAN PLUS 100ml.jpg", ["Nillzan Plus"]),
    ("nulcure.jpg", ["Nulcure"]),
    ("nyombe dcp 500g.jpg", ["Nyombe DCP"]),
    ("parastar 1L.jpg", ["Parastar"]),
    ("passcode.jpg", ["Passcode"]),
    ("PIPER 25G.jpg", ["Piper"]),
    ("Piperazine.jpg", ["Piperazine"]),
    ("POLLYSEL 125ML.jpg", ["Pollysel"]),
    ("saline.jpg", ["Saline"]),
    ("SEVIN.jpg", ["Sevin"]),
    ("Truvet.jpg", ["Truvet"]),
    ("Twelve.jpg", ["Twelve"]),
    ("twiga lick max.jpg", ["Twiga lick max"]),
    ("twiga stocklick 2kgs.jpg", ["Twiga stock lick"]),
    ("Twigalicl joto 1kg.jpg", ["Twiga lick manure"]),
    ("udder booster.jpg", ["Udder booster"]),
    ("ultramix joto.jpg", ["Udaminx"]),
    ("weedal 1L.jpg", ["Weedal"]),
]

class Command(BaseCommand):
    help = "Attach Static images to agrovet products using an explicit map"

    def handle(self, *a, **o):
        src = Path(settings.BASE_DIR).parent / "Static"
        dest = Path(settings.MEDIA_ROOT) / "products"
        dest.mkdir(parents=True, exist_ok=True)

        products = list(Product.objects.filter(sku__startswith="Agr"))
        by_name = {}
        for p in products:
            by_name.setdefault(p.name.strip().lower(), []).append(p)

        done = set()
        for fname, names in MAP:
            path = src / fname
            if not path.exists():
                self.stdout.write(self.style.WARNING(f"MISSING FILE  {fname}"))
                continue
            targets = [p for n in names for p in by_name.get(n.lower(), []) if p.pk not in done]
            if not targets:
                self.stdout.write(self.style.WARNING(f"NO PRODUCT    {fname}  (looked for {names})"))
                continue
            safe = re.sub(r"[^A-Za-z0-9._-]+", "_", fname)
            shutil.copy(path, dest / safe)
            for p in targets:
                p.image.name = f"products/{safe}"
                p.save(update_fields=["image"])
                done.add(p.pk)
            self.stdout.write(f"OK  {fname}  ->  {len(targets)} product(s): {names[0]}")

        self.stdout.write(self.style.SUCCESS(
            f"\n{len(done)} of {len(products)} agrovet products now have images."))
