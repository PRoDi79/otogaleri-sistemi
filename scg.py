"""
scg.py - Oto galeri yönetim sistemi

Bu modül araç ekleme, güncelleme, silme ve satış işlemlerini
yöneten OtoGaleri sınıfını içerir. Düzenleme (güncelleme/silme)
işlemleri için parola doğrulama entegre edilmiştir.

Yedekleme/kalıcılık için basit JSON dosyası (galeri_data.json) kullanılır.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, List, Optional


class Arac:
    """Basit araç verisi yapısı."""

    def __init__(self, plaka: str, model: str, yil: int, fiyat: float, adet: int = 1):
        self.plaka = plaka
        self.model = model
        self.yil = yil
        self.fiyat = float(fiyat)
        self.adet = int(adet)

    def to_dict(self) -> Dict:
        return {
            "plaka": self.plaka,
            "model": self.model,
            "yil": self.yil,
            "fiyat": self.fiyat,
            "adet": self.adet,
        }

    @staticmethod
    def from_dict(data: Dict) -> "Arac":
        return Arac(
            plaka=data["plaka"],
            model=data["model"],
            yil=int(data["yil"]),
            fiyat=float(data["fiyat"]),
            adet=int(data.get("adet", 1)),
        )


class OtoGaleri:
    """Oto galeri yönetimi.

    Özellikler:
    - araç ekleme/güncelleme/silme
    - satış işlemleri (satis_islemleri)
    - basit JSON ile kalıcılık
    - düzenleme (güncelleme/silme) için parola doğrulama
    """

    def __init__(self, data_file: str = "galeri_data.json", edit_password: Optional[str] = None):
        self.data_file = data_file
        self.edit_password = edit_password or "admin123"  # Varsayılan düzenleme şifresi; üretimde değiştirin
        self.araclar: Dict[str, Arac] = {}  # plaka -> Arac
        self.satis_kaydi: List[Dict] = []
        self._load()

    # --- Kalıcılık ---
    def _load(self) -> None:
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            for a in data.get("araclar", []):
                arac = Arac.from_dict(a)
                self.araclar[arac.plaka] = arac
            self.satis_kaydi = data.get("satis_kaydi", [])
        except FileNotFoundError:
            # Yeni sistem; dosya yoksa baştan başla
            self.araclar = {}
            self.satis_kaydi = []
        except Exception:
            # Hata alındıysa, temiz başlat
            self.araclar = {}
            self.satis_kaydi = []

    def _save(self) -> None:
        data = {
            "araclar": [a.to_dict() for a in self.araclar.values()],
            "satis_kaydi": self.satis_kaydi,
        }
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # --- Yönetim işlemleri (düzenleme şifresi ile korumalı) ---
    def _check_edit_password(self, password: Optional[str]) -> bool:
        return bool(password) and password == self.edit_password

    def arac_ekle(self, arac: Arac) -> None:
        """Yeni araç ekler; aynı plakaya sahipse adet artırılır."""
        if arac.plaka in self.araclar:
            mevcut = self.araclar[arac.plaka]
            mevcut.adet += arac.adet
        else:
            self.araclar[arac.plaka] = arac
        self._save()

    def arac_guncelle(self, plaka: str, model: Optional[str] = None, yil: Optional[int] = None,
                      fiyat: Optional[float] = None, adet: Optional[int] = None,
                      password: Optional[str] = None) -> bool:
        """Araç bilgilerini günceller. Başarılıysa True döner.

        Güncelleme işlemi için düzenleme şifresi gereklidir.
        """
        if not self._check_edit_password(password):
            raise PermissionError("Geçersiz düzenleme şifresi.")
        arac = self.araclar.get(plaka)
        if not arac:
            return False
        if model is not None:
            arac.model = model
        if yil is not None:
            arac.yil = int(yil)
        if fiyat is not None:
            arac.fiyat = float(fiyat)
        if adet is not None:
            arac.adet = int(adet)
        self._save()
        return True

    def arac_sil(self, plaka: str, password: Optional[str] = None) -> bool:
        """Plakaya göre aracı siler (tamamını). Düzenleme şifresi gerekir."""
        if not self._check_edit_password(password):
            raise PermissionError("Geçersiz düzenleme şifresi.")
        if plaka in self.araclar:
            del self.araclar[plaka]
            self._save()
            return True
        return False

    def stok_listele(self) -> List[Dict]:
        """Mevcut stok listesini döner."""
        return [a.to_dict() for a in self.araclar.values()]

    # --- Satış işlemleri ---
    def satis_islemleri(self, plaka: str, adet: int = 1, odeme_tipi: str = "Nakit") -> Dict:
        """
        Bir araç satışı gerçekleştirir.

        İşleyiş:
        - Belirtilen plakada araç var mı kontrol edilir.
        - İstenen adet kadar stokta varsa adet düşürülür ve satış kaydedilir.
        - Stokta yeterli adet yoksa hata fırlatılır.

        Parametreler:
        - plaka: satılacak aracın plakası
        - adet: satılacak adet (varsayılan 1)
        - odeme_tipi: ödeme yöntemi (örn. "Nakit", "Kredi Kartı")

        Dönen değer:
        - satışın özetini içeren sözlük (fiyat, toplam_tutar, kalan_adet, tarih, ödeme tipi)
        """
        if adet <= 0:
            raise ValueError("Satış adedi 1 veya daha büyük olmalıdır.")

        arac = self.araclar.get(plaka)
        if not arac:
            raise KeyError(f"Plaka bulunamadı: {plaka}")

        if arac.adet < adet:
            raise ValueError(f"Yetersiz stok: istenen {adet}, mevcut {arac.adet}")

        # Hesapla
        toplam_tutar = round(arac.fiyat * adet, 2)

        # Stok güncelle
        arac.adet -= adet
        if arac.adet == 0:
            # Tercihe bağlı: stoğu bittiyse kayıtta bırakılır, ancak silinmesi de tercih edilebilir
            pass

        # Satış kaydı
        satis = {
            "plaka": plaka,
            "model": arac.model,
            "adet": adet,
            "birim_fiyat": arac.fiyat,
            "toplam_tutar": toplam_tutar,
            "odeme_tipi": odeme_tipi,
            "tarih": datetime.utcnow().isoformat() + "Z",
        }
        self.satis_kaydi.append(satis)
        self._save()

        # Fatura/fiş özeti
        fatura = {
            "mesaj": "Satış başarıyla gerçekleştirildi.",
            "plaka": plaka,
            "model": arac.model,
            "adet": adet,
            "birim_fiyat": arac.fiyat,
            "toplam_tutar": toplam_tutar,
            "kalan_adet": arac.adet,
            "odeme_tipi": odeme_tipi,
            "tarih": satis["tarih"],
        }
        return fatura


# Eğer bu modül doğrudan çalıştırılırsa küçük bir demo yapabiliriz.
if __name__ == "__main__":
    g = OtoGaleri(edit_password="sifre123")
    # Örnek araç ekleme
    g.arac_ekle(Arac(plaka="34ABC34", model="Test Model", yil=2020, fiyat=250000, adet=2))
    print("Stok:", g.stok_listele())
    # Satış
    try:
        f = g.satis_islemleri(plaka="34ABC34", adet=1, odeme_tipi="Kredi Kartı")
        print("Fatura:", f)
    except Exception as e:
        print("Hata:", e)
