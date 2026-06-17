import random
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

COLORS = ["kirmizi", "sari", "mavi", "siyah"]
COLOR_NAMES  = {"kirmizi": "Kırmızı", "sari": "Sarı", "mavi": "Mavi", "siyah": "Siyah"}
COLOR_EMOJI  = {"kirmizi": "🔴", "sari": "🟡", "mavi": "🔵", "siyah": "⚫"}

COLOR_INPUT_MAP = {
    "kirmizi": "kirmizi", "kırmızı": "kirmizi", "k": "kirmizi", "red": "kirmizi",
    "sari": "sari", "sarı": "sari", "s": "sari", "yellow": "sari",
    "mavi": "mavi", "m": "mavi", "blue": "mavi",
    "siyah": "siyah", "si": "siyah", "black": "siyah",
}

class GameState(Enum):
    WAITING  = "waiting"
    PLAYING  = "playing"
    FINISHED = "finished"

@dataclass
class Tas:
    renk: str
    sayi: int
    okey: bool = False

    def __str__(self):
        if self.okey:
            return "🃏OKEY"
        return f"{COLOR_EMOJI[self.renk]}{self.sayi}"

    def __eq__(self, other):
        if not isinstance(other, Tas):
            return False
        return self.renk == other.renk and self.sayi == other.sayi and self.okey == other.okey

    def __hash__(self):
        return hash((self.renk, self.sayi, self.okey))

def create_okey_set() -> list[Tas]:
    seti = []
    for _ in range(2):
        for renk in COLORS:
            for sayi in range(1, 14):
                seti.append(Tas(renk=renk, sayi=sayi))
    seti.append(Tas(renk="kirmizi", sayi=0, okey=True))
    seti.append(Tas(renk="sari",    sayi=0, okey=True))
    return seti

def determine_okey_tas(goster: Tas) -> Tas:
    if goster.okey:
        return Tas(renk="kirmizi", sayi=1)
    ns = goster.sayi + 1
    if ns > 13:
        ns = 1
    return Tas(renk=goster.renk, sayi=ns)

def sort_hand_renk_sayi(el: list[Tas]) -> list[Tas]:
    """Aynı renk, ardışık sayı sıralaması (1-2-3 / kırmızı)."""
    renk_order = {"kirmizi": 0, "sari": 1, "mavi": 2, "siyah": 3}
    def key(t: Tas):
        if t.okey:
            return (99, 99)
        return (renk_order.get(t.renk, 9), t.sayi)
    return sorted(el, key=key)

def sort_hand_sayi_renk(el: list[Tas]) -> list[Tas]:
    """Aynı sayı, farklı renk sıralaması (13🔴 13🟡 13🔵)."""
    renk_order = {"kirmizi": 0, "sari": 1, "mavi": 2, "siyah": 3}
    def key(t: Tas):
        if t.okey:
            return (99, 99)
        return (t.sayi, renk_order.get(t.renk, 9))
    return sorted(el, key=key)

def sort_hand(el: list[Tas], okey_tas=None) -> list[Tas]:
    return sort_hand_renk_sayi(el)

def check_winner(el: list[Tas], okey_tas: Optional[Tas]) -> bool:
    if len(el) < 14:
        return False
    hand   = [t for t in el if not t.okey]
    jokers = len([t for t in el if t.okey])
    if okey_tas:
        okeys   = [t for t in hand if t.renk == okey_tas.renk and t.sayi == okey_tas.sayi]
        hand    = [t for t in hand if not (t.renk == okey_tas.renk and t.sayi == okey_tas.sayi)]
        jokers += len(okeys)
    return jokers >= len(hand) // 3

@dataclass
class OkeyGame:
    masa_id: str
    oyuncular:       list[int]          = field(default_factory=list)
    oyuncu_elleri:   dict[int, list]    = field(default_factory=dict)
    oyuncu_adlari:   dict[int, str]     = field(default_factory=dict)
    talon:           list[Tas]          = field(default_factory=list)
    cop_yigi:        list[Tas]          = field(default_factory=list)
    goster_tas:      Optional[Tas]      = None
    okey_tas:        Optional[Tas]      = None
    siradaki_oyuncu: int                = 0
    durum:           GameState          = GameState.WAITING
    bahis:           int                = 0
    max_oyuncu:      int                = 4
    sifreli:         bool               = False
    sifre:           str                = ""
    kanal_id:        Optional[int]      = None
    oyun_kanal_id:   Optional[int]      = None
    mesaj_id:        Optional[int]      = None
    panel_mesaj_id:  Optional[int]      = None
    izleyiciler:     list[int]          = field(default_factory=list)
    bot_oyuncular:   set[int]           = field(default_factory=set)
    el_cekti:        dict[int, bool]    = field(default_factory=dict)
    mesaj_sayaci:    int                = 0
    bot_modu:        object             = False
    diskalifiye:     set[int]           = field(default_factory=set)  # DK olan gerçek oyuncular

    def oyuncu_ekle(self, user_id: int, ad: str) -> bool:
        if user_id in self.oyuncular:
            return False
        if len(self.oyuncular) >= self.max_oyuncu:
            return False
        self.oyuncular.append(user_id)
        self.oyuncu_adlari[user_id] = ad
        self.el_cekti[user_id] = False
        return True

    def oyuncu_cikar(self, user_id: int) -> bool:
        if user_id not in self.oyuncular:
            return False
        self.oyuncular.remove(user_id)
        if user_id in self.oyuncu_elleri:
            self.talon.extend(self.oyuncu_elleri.pop(user_id))
            random.shuffle(self.talon)
        return True

    def doldur_botlarla(self):
        bot_ids  = [-1, -2, -3, -4]
        bot_adl  = ["🤖 Bot Ahmet", "🤖 Bot Mehmet", "🤖 Bot Ayşe", "🤖 Bot Fatma"]
        for bid, bad in zip(bot_ids, bot_adl):
            if len(self.oyuncular) >= self.max_oyuncu:
                break
            if bid not in self.oyuncular:
                self.oyuncular.append(bid)
                self.oyuncu_adlari[bid] = bad
                self.bot_oyuncular.add(bid)
                self.el_cekti[bid] = False

    def oyunu_baslat(self):
        if len(self.oyuncular) < 2:
            return False
        seti = create_okey_set()
        random.shuffle(seti)
        self.goster_tas = seti.pop()
        self.okey_tas   = determine_okey_tas(self.goster_tas)
        # İlk oyuncu 14 taş alır (taş çekmez), diğerleri 13 alır
        for i, oyuncu in enumerate(self.oyuncular):
            adet = 14 if i == 0 else 13
            self.oyuncu_elleri[oyuncu] = sort_hand(seti[:adet], self.okey_tas)
            seti = seti[adet:]
            # İlk oyuncu zaten 14 taşa sahip — bu turda taş çekmez
            self.el_cekti[oyuncu] = (i == 0)
        self.talon = seti
        random.shuffle(self.talon)
        self.cop_yigi = []
        self.siradaki_oyuncu = 0
        self.durum = GameState.PLAYING
        return True

    def siradaki_oyuncu_id(self) -> Optional[int]:
        if not self.oyuncular:
            return None
        return self.oyuncular[self.siradaki_oyuncu % len(self.oyuncular)]

    def _tur_bitir(self, user_id: int):
        self.el_cekti[user_id] = False
        self.siradaki_oyuncu   = (self.siradaki_oyuncu + 1) % len(self.oyuncular)

    def talon_cek(self, user_id: int) -> Optional[Tas]:
        if not self.talon:                            return None
        if self.siradaki_oyuncu_id() != user_id:     return None
        if self.el_cekti.get(user_id):               return None
        tas = self.talon.pop(0)
        self.oyuncu_elleri[user_id].append(tas)
        self.oyuncu_elleri[user_id] = sort_hand(self.oyuncu_elleri[user_id], self.okey_tas)
        self.el_cekti[user_id] = True
        return tas

    # "Tablodaki son taşı al" — çöp yığının tepesini çek
    def son_tasi_al(self, user_id: int) -> Optional[Tas]:
        if not self.cop_yigi:                         return None
        if self.siradaki_oyuncu_id() != user_id:     return None
        if self.el_cekti.get(user_id):               return None
        tas = self.cop_yigi.pop()
        self.oyuncu_elleri[user_id].append(tas)
        self.oyuncu_elleri[user_id] = sort_hand(self.oyuncu_elleri[user_id], self.okey_tas)
        self.el_cekti[user_id] = True
        return tas

    def tas_at_by_renk_sayi(self, user_id: int, renk: str, sayi: int) -> Optional[Tas]:
        if self.siradaki_oyuncu_id() != user_id:     return None
        if not self.el_cekti.get(user_id):           return None
        el = self.oyuncu_elleri.get(user_id, [])
        for i, t in enumerate(el):
            if not t.okey and t.renk == renk and t.sayi == sayi:
                el.pop(i)
                self.cop_yigi.append(t)
                self._tur_bitir(user_id)
                return t
        return None

    def tas_at(self, user_id: int, idx: int) -> Optional[Tas]:
        if self.siradaki_oyuncu_id() != user_id:     return None
        if not self.el_cekti.get(user_id):           return None
        el = self.oyuncu_elleri.get(user_id, [])
        if idx < 0 or idx >= len(el):                return None
        tas = el.pop(idx)
        self.cop_yigi.append(tas)
        self._tur_bitir(user_id)
        return tas

    def peri_diz(self, user_id: int, mod: str = "renk_sayi"):
        if user_id not in self.oyuncu_elleri:
            return
        if mod == "sayi_renk":
            self.oyuncu_elleri[user_id] = sort_hand_sayi_renk(self.oyuncu_elleri[user_id])
        else:
            self.oyuncu_elleri[user_id] = sort_hand_renk_sayi(self.oyuncu_elleri[user_id])

    def okey_ac(self, user_id: int) -> bool:
        if self.siradaki_oyuncu_id() != user_id:     return False
        if not self.el_cekti.get(user_id):           return False
        el = self.oyuncu_elleri.get(user_id, [])
        if check_winner(el, self.okey_tas):
            self.durum = GameState.FINISHED
            return True
        return False

    def bot_hamle_yap(self, bot_id: int) -> Optional[Tas]:
        if self.siradaki_oyuncu_id() != bot_id:      return None
        if not self.el_cekti.get(bot_id):
            if self.talon:
                self.talon_cek(bot_id)
            else:
                return None
        el = self.oyuncu_elleri.get(bot_id, [])
        if not el:
            return None
        if check_winner(el, self.okey_tas):
            self.durum = GameState.FINISHED
            return None
        return self.tas_at(bot_id, self._bot_en_kotu(bot_id))

    def _bot_en_kotu(self, bot_id: int) -> int:
        el = self.oyuncu_elleri.get(bot_id, [])
        for i, t in enumerate(el):
            if t.okey:
                continue
            if self.okey_tas and t.renk == self.okey_tas.renk and t.sayi == self.okey_tas.sayi:
                continue
            puan = 0
            for j, d in enumerate(el):
                if i == j:
                    continue
                if d.renk == t.renk and abs(d.sayi - t.sayi) <= 2:
                    puan += 1
                if d.sayi == t.sayi:
                    puan += 1
            if puan == 0:
                return i
        return len(el) - 1

    @property
    def doluluk(self) -> str:
        gercek = len([u for u in self.oyuncular if u > 0])
        return f"{gercek}/{self.max_oyuncu}"
