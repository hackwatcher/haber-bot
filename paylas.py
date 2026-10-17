"""Instagram'a tek görsel ya da karusel gönderi. Son Koz botundaki (bugunbasla/bot.py) Graph akışının sade hali.

yontem "meta": graph.facebook.com + sistem kullanıcısı token'ı; hesap Facebook sayfasına bağlı İşletme hesabı olmalı.
yontem "instagram": graph.instagram.com + Instagram ile giriş token'ı.
Instagram görseli adresten indirir; görseller herkese açık bir GitHub reposunun 'media' dalına konur.
"""

import datetime as dt
import json
import os
import shutil
import subprocess
import tempfile
import time

import requests

KOK = os.path.dirname(os.path.abspath(__file__))
ADRES = {"meta": "https://graph.facebook.com/v26.0/", "instagram": "https://graph.instagram.com/v23.0/"}


def token_oku(ig):
    # GitHub'da secret (META_TOKEN), bilgisayarda .gizli/token.txt
    tok = (os.environ.get("META_TOKEN") or os.environ.get("HABER_TOKEN") or "").strip()
    yol = os.path.join(KOK, ig["token_dosyasi"])
    if not tok and os.path.exists(yol):
        with open(yol, encoding="utf-8") as f:
            tok = f.read().strip()
    if not tok:
        raise RuntimeError(f"Token yok: {ig['token_dosyasi']} dosyasına token'ı yapıştır.")
    return tok


class Instagram:
    def __init__(self, ig):
        self.ayar = ig
        self.base = ADRES[ig["yontem"]]
        self.token = token_oku(ig)
        self._id = None

    def call(self, method, path, **params):
        params["access_token"] = self.token
        try:
            if method == "GET":
                r = requests.get(self.base + path, params=params, timeout=120)
            else:
                r = requests.post(self.base + path, data=params, timeout=120)
            data = r.json()
        except Exception as e:  # token görünmesin
            raise RuntimeError(f"{path}: istek başarısız: {str(e).replace(self.token, '***')}") from None
        if "error" in data:
            e = data["error"]
            raise RuntimeError(f"{e.get('error_user_title') or e.get('message')} {e.get('error_user_msg', '')} "
                               f"(kod {e.get('code')}/{e.get('error_subcode', '-')})")
        return data

    @property
    def ig(self):
        if self._id:
            return self._id
        if self.ayar["yontem"] == "instagram":
            self._id = self.call("GET", "me", fields="user_id")["user_id"]
            return self._id
        r = self.call("GET", "me/accounts", fields="name,instagram_business_account{id,username}", limit="50")
        for s in r.get("data", []):
            hesap = s.get("instagram_business_account")
            if hesap and hesap.get("username") == self.ayar["kullanici_adi"]:
                self._id = hesap["id"]
                return self._id
        raise RuntimeError(f"@{self.ayar['kullanici_adi']} bulunamadı: İşletme hesabı + bağlı Facebook sayfası + "
                           f"token'da sayfa yetkisi gerekli.")

    def baglanti(self):
        b = self.call("GET", self.ig, fields="username,media_count,followers_count")
        return f"@{b['username']} · {b.get('media_count', 0)} gönderi · {b.get('followers_count', 0)} takipçi"

    def facebook_kontrol(self):
        """Token'ın Facebook izinlerini ve bağlı sayfaları sorgular (Salt okunur)."""
        sonuc = {}
        try:
            izinler = self.call("GET", "me/permissions").get("data", [])
            sonuc["izinler"] = [p["permission"] for p in izinler if p.get("status") == "granted"]
        except Exception as e:
            sonuc["izin_hatasi"] = str(e)
        try:
            r = self.call("GET", "me/accounts", fields="id,name,access_token,tasks,instagram_business_account{username}", limit="50")
            sayfalar = []
            for s in r.get("data", []):
                p_tok = s.get("access_token")
                yazma_testi = "token_yok"
                if p_tok:
                    try:
                        r_perm = requests.get(f"https://graph.facebook.com/v26.0/me/permissions?access_token={p_tok}", timeout=10).json()
                        p_perms = [p["permission"] for p in r_perm.get("data", []) if p.get("status") == "granted"]
                        yazma_testi = p_perms
                    except Exception as err:
                        yazma_testi = str(err)
                sayfalar.append({
                    "id": s["id"],
                    "ad": s["name"],
                    "gorevler": s.get("tasks", []),
                    "sayfa_izinleri": yazma_testi,
                    "bagli_ig": s.get("instagram_business_account", {}).get("username")
                })
            sonuc["sayfalar"] = sayfalar
        except Exception as e:
            sonuc["sayfa_hatasi"] = str(e)
        return sonuc

    def bekle(self, cid, sure=180):
        bas = time.time()
        while time.time() - bas < sure:
            s = self.call("GET", cid, fields="status_code").get("status_code")
            if s == "FINISHED":
                return
            if s in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"Instagram görseli işleyemedi ({s})")
            time.sleep(3)
        raise RuntimeError("Instagram görseli zamanında işlemedi")

    def son_gonderi(self, sonra, kenar="media"):
        try:
            for m in self.call("GET", f"{self.ig}/{kenar}", fields="id,timestamp", limit="3").get("data", []):
                if dt.datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%S%z") >= sonra:
                    return m["id"]
        except RuntimeError:
            pass
        return None

    def yayimla(self, cid, kenar="media"):
        """Hazır kapsayıcıyı yayımlar; hata dönse de yayın gerçekleşmişse onu döndürür (çift paylaşım olmasın)."""
        sonra = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=30)
        for i in range(3):
            try:
                return self.call("POST", f"{self.ig}/media_publish", creation_id=cid)["id"]
            except RuntimeError:
                bulunan = self.son_gonderi(sonra, kenar)
                if bulunan:
                    return bulunan
                if i == 2:
                    raise
                time.sleep(10 * (i + 1))

    def yorum_yap(self, media_id, mesaj):
        """Gönderiye ya da Reels'e hesap adına ilk yorumu ekler. Yorum ID'sini döndürür."""
        if not media_id or not mesaj:
            return None
        r = self.call("POST", f"{media_id}/comments", message=mesaj)
        return r.get("id")


    def reels(self, video_url, aciklama, akisa=False):
        cid = self.call("POST", f"{self.ig}/media", media_type="REELS", video_url=video_url, caption=aciklama,
                        share_to_feed="true" if akisa else "false")["id"]
        self.bekle(cid, sure=420)
        return self.yayimla(cid)

    def story(self, gorsel_url):
        cid = self.call("POST", f"{self.ig}/media", media_type="STORIES", image_url=gorsel_url)["id"]
        self.bekle(cid)
        return self.yayimla(cid, kenar="stories")

    def gonder(self, gorsel_urlleri, aciklama):
        """Tek görsel ya da (2-10 görsel/video) karma medya karusel gönderi yayımlar."""
        if len(gorsel_urlleri) == 1:
            u = gorsel_urlleri[0]
            if u.lower().endswith(".mp4"):
                cid = self.call("POST", f"{self.ig}/media", media_type="VIDEO", video_url=u, caption=aciklama)["id"]
            else:
                cid = self.call("POST", f"{self.ig}/media", image_url=u, caption=aciklama)["id"]
        else:
            cocuklar = []
            for u in gorsel_urlleri[:10]:
                if u.lower().endswith(".mp4"):
                    cid_c = self.call("POST", f"{self.ig}/media", media_type="VIDEO", video_url=u, is_carousel_item="true")["id"]
                else:
                    cid_c = self.call("POST", f"{self.ig}/media", image_url=u, is_carousel_item="true")["id"]
                cocuklar.append(cid_c)
            for c in cocuklar:
                self.bekle(c, sure=300)
            cid = self.call("POST", f"{self.ig}/media", media_type="CAROUSEL", children=",".join(cocuklar),
                            caption=aciklama)["id"]
        self.bekle(cid)
        return self.yayimla(cid)


def gh_token():
    tok = (os.environ.get("MEDIA_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()
    if tok:
        return tok
    r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError("GitHub token'ı yok: 'gh auth login' yap ya da MEDIA_TOKEN ayarla.")
    return r.stdout.strip()


def github_yukle(yollar, repo):
    """Görselleri herkese açık repodaki 'media' dalına koyar, kalıcı adreslerini döndürür."""
    token = gh_token()
    is_ = tempfile.mkdtemp()
    try:
        adlar = [f"{i:02d}{os.path.splitext(y)[1]}" for i, y in enumerate(yollar, 1)]
        for yol, ad in zip(yollar, adlar):
            shutil.copy(yol, os.path.join(is_, ad))
        kimlik = ["-c", "user.name=haberbot", "-c", "user.email=bot@users.noreply.github.com"]
        for args in (["init", "-q", "-b", "media"], [*kimlik, "add", "."], [*kimlik, "commit", "-q", "-m", "media"]):
            subprocess.run(["git", *args], cwd=is_, check=True, capture_output=True)
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=is_, check=True,
                             capture_output=True, text=True).stdout.strip()
        r = subprocess.run(["git", "push", "-q", "--force", f"https://x-access-token:{token}@github.com/{repo}.git",
                            "HEAD:media"], cwd=is_, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("Görsel GitHub'a gönderilemedi: " + r.stderr.replace(token, "***"))
    finally:
        shutil.rmtree(is_, ignore_errors=True)
    urller = [f"https://raw.githubusercontent.com/{repo}/{sha}/{ad}" for ad in adlar]
    for url in urller:
        for _ in range(20):
            if requests.head(url, timeout=20).status_code == 200:
                break
            time.sleep(3)
        else:
            raise RuntimeError(f"Görsel açılmıyor (repo herkese açık mı?): {url}")
    return urller


def paylas(gorseller, aciklama, cfg, video=None, story=None, ilk_yorum=None):
    """Gönderi (tek kart/karusel), sonra Reels ve story. {"gonderi": id, "reels": id|hata, "story": id|hata, "yorum": id|hata} döner.

    Gönderi başarısızsa hata fırlatır; Reels/story/yorum hatası gönderiyi geri almaz, sadece kaydedilir.
    """
    ig = cfg["instagram"]
    istemci = Instagram(ig)
    repo = os.environ.get("MEDIA_REPO") or os.environ.get("GITHUB_REPOSITORY") or ig["gorsel_repo"]
    ekler = [y for y in (video, story) if y]
    urller = github_yukle(list(gorseller) + ekler, repo)  # hepsi tek seferde
    gorsel_url, ek_url = urller[:len(gorseller)], dict(zip(ekler, urller[len(gorseller):]))
    sonuc = {"gonderi": istemci.gonder(gorsel_url, aciklama)}
    if video:
        try:
            sonuc["reels"] = istemci.reels(ek_url[video], aciklama, akisa=cfg.get("reels", {}).get("akisa_da", False))
        except Exception as e:
            sonuc["reels"] = f"hata: {e}"
    if story:
        try:
            sonuc["story"] = istemci.story(ek_url[story])
        except Exception as e:
            sonuc["story"] = f"hata: {e}"
    if ilk_yorum:
        if sonuc.get("gonderi") and not str(sonuc["gonderi"]).startswith("hata"):
            try:
                sonuc["yorum"] = istemci.yorum_yap(sonuc["gonderi"], ilk_yorum)
            except Exception as e:
                sonuc["yorum"] = f"hata: {e}"
        if sonuc.get("reels") and not str(sonuc["reels"]).startswith("hata"):
            try:
                istemci.yorum_yap(sonuc["reels"], ilk_yorum)
            except Exception:
                pass
    return sonuc


if __name__ == "__main__":
    with open(os.path.join(KOK, "config.json"), encoding="utf-8") as f:
        print(Instagram(json.load(f)["instagram"]).baglanti())
