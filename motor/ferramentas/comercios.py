"""Buscador de 'comércios sem site'.

Fontes:
  * Google Places API (New) — se GOOGLE_MAPS_API_KEY existir: Text Search com campo websiteUri.
  * OpenStreetMap / Overpass (grátis) — fallback: busca por tags OSM (shop=bakery etc.) dentro da cidade.
Um comércio é marcado "sem_site" quando não há website/contact:website/url/facebook/instagram no cadastro.
(No OSM a ausência da tag não garante que não exista site; por isso há 'verificar_site' opcional via busca web.)
"""
import csv, json, os, re, time
from ..net import http, http_json, q
from ..registro import ferramenta
from .util import pasta, slug

CATEGORIAS = {   # pt-BR -> filtros Overpass
    "padaria": ['"shop"="bakery"'], "padarias": ['"shop"="bakery"'],
    "restaurante": ['"amenity"="restaurant"'], "restaurantes": ['"amenity"="restaurant"'],
    "lanchonete": ['"amenity"="fast_food"'], "lanchonetes": ['"amenity"="fast_food"'],
    "bar": ['"amenity"="bar"'], "bares": ['"amenity"="bar"', '"amenity"="pub"'],
    "cafe": ['"amenity"="cafe"'], "cafeteria": ['"amenity"="cafe"'],
    "mercado": ['"shop"="supermarket"', '"shop"="convenience"'], "mercados": ['"shop"="supermarket"', '"shop"="convenience"'],
    "farmacia": ['"amenity"="pharmacy"'], "farmácia": ['"amenity"="pharmacy"'], "farmacias": ['"amenity"="pharmacy"'],
    "salao": ['"shop"="hairdresser"'], "salão de beleza": ['"shop"="hairdresser"'], "barbearia": ['"shop"="hairdresser"'],
    "oficina": ['"shop"="car_repair"'], "oficinas": ['"shop"="car_repair"'],
    "academia": ['"leisure"="fitness_centre"'], "pet shop": ['"shop"="pet"'], "açougue": ['"shop"="butcher"'],
    "roupas": ['"shop"="clothes"'], "loja de roupas": ['"shop"="clothes"'], "sorveteria": ['"amenity"="ice_cream"'],
}
ESPELHOS = ["https://overpass-api.de/api/interpreter", "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter", "https://overpass.private.coffee/api/interpreter"]
SITE_TAGS = ["website", "contact:website", "url", "contact:facebook", "facebook", "contact:instagram", "instagram"]


def _overpass(consulta):
    erro = None
    for url in ESPELHOS:
        try:
            return json.loads(http(url, "data=" + q(consulta), timeout=90))
        except Exception as e:
            erro = e; time.sleep(1)
    raise RuntimeError(f"Overpass indisponível: {erro}")


RAIO_M = int(os.environ.get("JARVIS_RAIO_M", "12000"))


def geocodificar(cidade):
    """Centro da cidade via Nominatim (OSM). Aceita 'Cidade' ou 'Cidade, UF'."""
    alvo = cidade if "," in cidade else cidade + ", Brasil"
    r = http_json(f"https://nominatim.openstreetmap.org/search?q={q(alvo)}&format=json&limit=1&countrycodes=br")
    if not r: raise ValueError(f"cidade não encontrada: {cidade}")
    return float(r[0]["lat"]), float(r[0]["lon"])


def _osm(cidade, categoria, limite):
    filtros = CATEGORIAS.get(categoria.lower().strip())
    if not filtros: raise ValueError(f"categoria não mapeada para OSM: {categoria}. Opções: {sorted(set(CATEGORIAS))}")
    lat, lon = geocodificar(cidade)
    # busca por raio em volta do centro da cidade: bem mais leve que area["name"=...] nos servidores Overpass
    partes = "".join(f"nwr[{f}](around:{RAIO_M},{lat},{lon});" for f in filtros)
    consulta = f'[out:json][timeout:60];({partes});out center tags {limite * 4};'
    dados = _overpass(consulta)
    out = []
    for e in dados.get("elements", []):
        t = e.get("tags", {})
        if not t.get("name"): continue
        lat = e.get("lat") or e.get("center", {}).get("lat"); lon = e.get("lon") or e.get("center", {}).get("lon")
        end = " ".join(x for x in [t.get("addr:street"), t.get("addr:housenumber"), t.get("addr:suburb")] if x)
        site = next((t[k] for k in SITE_TAGS if t.get(k)), "")
        out.append({"nome": t["name"], "categoria": categoria, "cidade": cidade, "endereco": end,
                    "telefone": t.get("phone") or t.get("contact:phone") or t.get("contact:whatsapp", ""),
                    "horario": t.get("opening_hours", ""), "site": site, "sem_site": not site,
                    "lat": lat, "lon": lon, "fonte": f"osm:{e['type']}/{e['id']}",
                    "mapa": f"https://www.openstreetmap.org/{e['type']}/{e['id']}"})
    return out


def _places(cidade, categoria, limite, chave):
    r = http_json("https://places.googleapis.com/v1/places:searchText", {"textQuery": f"{categoria} em {cidade}", "languageCode": "pt-BR", "pageSize": min(20, limite)},
                  {"X-Goog-Api-Key": chave, "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.websiteUri,places.location,places.googleMapsUri,places.rating"})
    return [{"nome": p["displayName"]["text"], "categoria": categoria, "cidade": cidade, "endereco": p.get("formattedAddress", ""),
             "telefone": p.get("nationalPhoneNumber", ""), "horario": "", "site": p.get("websiteUri", ""), "sem_site": not p.get("websiteUri"),
             "lat": p["location"]["latitude"], "lon": p["location"]["longitude"], "fonte": "google_places",
             "mapa": p.get("googleMapsUri", ""), "nota": p.get("rating")} for p in r.get("places", [])]


@ferramenta(risco="arquivo")
def buscar_comercios_sem_site(cidade: str, categoria: str, limite: int = 60, verificar_web: bool = False):
    """Busca comércios locais (Google Places ou OpenStreetMap) por cidade+categoria, marca os sem site e exporta CSV."""
    categoria = re.sub(r"^(de|da|do|das|dos)\s+", "", categoria.strip().lower())
    chave = os.environ.get("GOOGLE_MAPS_API_KEY")
    itens = _places(cidade, categoria, limite, chave) if chave else _osm(cidade, categoria, limite)
    itens = itens[:limite]
    if verificar_web:   # confere por busca web os 'sem site' (lento: 1 busca por item)
        from .web import pesquisar_web
        for it in [i for i in itens if i["sem_site"]][:15]:
            try:
                res = pesquisar_web(f'"{it["nome"]}" {cidade}', 3)["resultados"]
                hit = next((r["url"] for r in res if slug(it["nome"]).split("-")[0] in r["url"]), "")
                if hit: it["site_possivel"] = hit
            except Exception: pass
    sem = [i for i in itens if i["sem_site"]]
    arq = os.path.join(pasta("comercios"), f"{slug(cidade)}_{slug(categoria)}_sem_site.csv")
    campos = ["nome", "categoria", "cidade", "endereco", "telefone", "horario", "site", "sem_site", "lat", "lon", "mapa", "fonte"]
    with open(arq, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, campos, extrasaction="ignore", delimiter=";"); w.writeheader(); w.writerows(sem)
    with open(arq.replace(".csv", "_todos.json"), "w", encoding="utf-8") as f: json.dump(itens, f, ensure_ascii=False, indent=1)
    return {"ok": True, "fonte": "google_places" if chave else "openstreetmap", "total": len(itens), "sem_site": len(sem),
            "csv": arq, "amostra": sem[:8]}
