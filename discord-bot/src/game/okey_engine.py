import random
import itertools
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
from functools import lru_cache

COLORS = ["kirmizi", "sari", "mavi", "siyah"]
COLOR_NAMES  = {"kirmizi": "Kırmızı", "sari": "Sarı", "mavi": "Mavi", "siyah": "Siyah"}
COLOR_EMOJI  = {"kirmizi": "🔴", "sari": "🟡", "mavi": "🔵", "siyah": "⚫"}

COLOR_INPUT_MAP = {
    "kirmizi": "kirmizi", "kırmızı": "kirmizi", "k": "kirmizi", "red": "kirmizi",
    "sari": "sari", "sarı": "sari", "s": "sari", "yellow": "sari",
    "mavi": "mavi", "m": "mavi", "blue": "mavi",
    "siyah": "siyah", "si": "siyah", "black": "siyah",
}

# Kazanma bonusları
BONUS_NORMAL       = 200
BONUS_CIFTE_OKEY   = 500   # Sahte okeyı son taş olarak atarak kazanmak
BONUS_YEDI_CIFT    = 350   # 7 çift yaparak kazanmak

# Geriye uyumluluk için alias (yeni sistemde sahte_joker wildcard değil)
BONUS_SAHTE_JOKER  = BONUS_NORMAL

class GameState(Enum):
    WAITING  = "waiting"
    PLAYING  = "playing"
    FINISHED = "finished"

@dataclass
class Tas:
    renk: str
    sayi: int
    okey: bool = False              # True = fiziksel sahte okey taşı (üzerinde sayı/renk yok)
    gorsel_renk: Optional[str] = None
    gorsel_sayi: Optional[int] = None

    def __str__(self):
        if self.okey:
            # Sahte okey her zaman okey_tas kimliğini gösterir (gorsel set edilmişse)
            if self.gorsel_renk and self.gorsel_sayi:
                emoji = COLOR_EMOJI.get(self.gorsel_renk, "🃏")
                return f"{emoji}{self.gorsel_sayi}(🃏)"
            return "🃏"
        return f"{COLOR_EMOJI[self.renk]}{self.sayi}"

    def display_label(self, okey_tas=None) -> str:
        """El görüntüsünde insan okunur etiket."""
        if self.okey:
            if okey_tas:
                renk_ad = COLOR_NAMES.get(okey_tas.renk, okey_tas.renk)
                return f"Sahte Okey (= {renk_ad} {okey_tas.sayi})"
            return "Sahte Okey 🃏"
        return f"{COLOR_NAMES.get(self.renk, self.renk)} {self.sayi}"

    def __eq__(self, other):
        if not isinstance(other, Tas):
            return False
        return self.renk == other.renk and self.sayi == other.sayi and self.okey == other.okey

    def __hash__(self):
        return hash((self.renk, self.sayi, self.okey))

def create_okey_set() -> list[Tas]:
    """106 taşlık standart Okey seti: 4 renk × 13 sayı × 2 adet = 104 + 2 sahte okey."""
    seti = []
    for _ in range(2):
        for renk in COLORS:
            for sayi in range(1, 14):
                seti.append(Tas(renk=renk, sayi=sayi))
    seti.append(Tas(renk="kirmizi", sayi=0, okey=True))
    seti.append(Tas(renk="sari",    sayi=0, okey=True))
    return seti

def determine_okey_tas(goster: Tas) -> Tas:
    """Açılan gösterge taşının bir üst sayısı ve aynı rengi okey taşıdır."""
    if goster.okey:
        return Tas(renk="kirmizi", sayi=1)
    ns = goster.sayi + 1
    if ns > 13:
        ns = 1
    return Tas(renk=goster.renk, sayi=ns)

def sort_hand_renk_sayi(el: list[Tas]) -> list[Tas]:
    renk_order = {"kirmizi": 0, "sari": 1, "mavi": 2, "siyah": 3}
    def key(t: Tas):
        if t.okey:
            return (99, 99)
        return (renk_order.get(t.renk, 9), t.sayi)
    return sorted(el, key=key)

def sort_hand_sayi_renk(el: list[Tas]) -> list[Tas]:
    renk_order = {"kirmizi": 0, "sari": 1, "mavi": 2, "siyah": 3}
    def key(t: Tas):
        if t.okey:
            return (99, 99)
        return (t.sayi, renk_order.get(t.renk, 9))
    return sorted(el, key=key)

def sort_hand(el: list[Tas], okey_tas=None) -> list[Tas]:
    return sort_hand_renk_sayi(el)

# ─── Set validasyon yardımcıları ─────────────────────────────────────────────

@lru_cache(maxsize=4096)
def _try_partition(tiles: tuple, jokers: int) -> bool:
    """
    Backtracking: tiles (sorted tuple) ve jokers adet GERÇEK wildcard ile
    geçerli Okey perlerine bölünebilir mi?
    GERÇEK wildcard = fiziksel okey_tas taşları (her taşın yerine geçer).
    Sahte okey bu fonksiyona NORMAL taş olarak (okey_tas kimliğiyle) gelir.
    """
    if not tiles and jokers == 0:
        return True
    if not tiles or jokers < 0:
        return False

    first_renk, first_sayi = tiles[0]
    rest = tiles[1:]

    # ── GRUP dene: aynı sayı, farklı renkler, min 3 max 4
    same_sayi = [i for i, (r, s) in enumerate(rest) if s == first_sayi]

    for size in (3, 4):
        need = size - 1
        for num_real in range(min(need, len(same_sayi)), -1, -1):
            j_for_grup = need - num_real
            if j_for_grup > jokers:
                continue
            for combo in itertools.combinations(same_sayi, num_real):
                renkler = {first_renk}
                ok = True
                for ci in combo:
                    r = rest[ci][0]
                    if r in renkler:
                        ok = False
                        break
                    renkler.add(r)
                if not ok:
                    continue
                remaining = tuple(t for i, t in enumerate(rest) if i not in combo)
                if _try_partition(remaining, jokers - j_for_grup):
                    return True

    # ── SERİ dene: aynı renk, ardışık sayılar, min 3
    for size in range(3, 14):
        for off in range(size):
            start_sayi = first_sayi - off
            if start_sayi < 1:
                continue
            end_sayi = start_sayi + size - 1
            if end_sayi > 13:
                continue

            j_used = off
            if j_used > jokers:
                continue

            taken_in_rest: set[int] = set()
            possible = True

            for k in range(size):
                if k == off:
                    continue
                pos_sayi = start_sayi + k
                idx = next(
                    (i for i, (r, s) in enumerate(rest)
                     if i not in taken_in_rest and r == first_renk and s == pos_sayi),
                    None
                )
                if idx is not None:
                    taken_in_rest.add(idx)
                elif j_used < jokers:
                    j_used += 1
                else:
                    possible = False
                    break

            if possible:
                remaining = tuple(t for i, t in enumerate(rest) if i not in taken_in_rest)
                if _try_partition(remaining, jokers - j_used):
                    return True

    return False

def _to_sorted_tuples(tas_list: list[Tas]) -> tuple:
    renk_order = {"kirmizi": 0, "sari": 1, "mavi": 2, "siyah": 3}
    return tuple(sorted(
        [(t.renk, t.sayi) for t in tas_list],
        key=lambda x: (renk_order.get(x[0], 9), x[1])
    ))

def _check_yedi_cift(el: list[Tas], okey_tas: Optional[Tas]) -> bool:
    """
    7 çift kontrolü.
    - Gerçek okey_tas fiziksel taşları = wildcard (herhangi bir çifti tamamlar)
    - Sahte okey = okey_tas kimliğinde normal taş (wildcard DEĞİL)
    """
    if len(el) != 14:
        return False
    joker_count = 0
    normal = []
    for t in el:
        if not t.okey and okey_tas and t.renk == okey_tas.renk and t.sayi == okey_tas.sayi:
            # Gerçek fiziksel okey_tas taşı = wildcard
            joker_count += 1
        elif t.okey and okey_tas:
            # Sahte okey = okey_tas kimliği (wildcard DEĞİL, okey_tas gibi sayılır)
            normal.append((okey_tas.renk, okey_tas.sayi))
        elif not t.okey:
            normal.append((t.renk, t.sayi))
    counts = Counter(normal)
    pairs = sum(v // 2 for v in counts.values())
    singles = sum(v % 2 for v in counts.values())
    jokers_used = min(singles, joker_count)
    pairs += jokers_used
    joker_count -= jokers_used
    pairs += joker_count // 2
    return pairs >= 7

def _build_partition_tuples(el_14: list[Tas], okey_tas: Optional[Tas]) -> tuple:
    """
    14 taşlık eli partition için tuple haline getirir.
    - Sahte okey → okey_tas kimliğinde normal taş (tuple'a eklenir)
    - Gerçek okey_tas → wildcard (ayrı sayılır, tuple'a EKLENMEz)
    Returns: (normal_tuples, joker_count)
    """
    renk_order = {"kirmizi": 0, "sari": 1, "mavi": 2, "siyah": 3}
    joker_count = 0
    all_tiles = []
    for t in el_14:
        if not t.okey and okey_tas and t.renk == okey_tas.renk and t.sayi == okey_tas.sayi:
            # Gerçek fiziksel okey_tas = wildcard
            joker_count += 1
        elif t.okey and okey_tas:
            # Sahte okey = okey_tas kimliğinde normal taş
            all_tiles.append((okey_tas.renk, okey_tas.sayi))
        elif not t.okey:
            all_tiles.append((t.renk, t.sayi))
    all_tiles_t = tuple(sorted(all_tiles, key=lambda x: (renk_order.get(x[0], 9), x[1])))
    return all_tiles_t, joker_count

def _check_14_winner(el: list[Tas], okey_tas: Optional[Tas]) -> tuple[bool, str]:
    """
    14 taşlık elin kazanıp kazanmadığını kontrol eder.
    Kazanma türleri: 'normal' | 'yedi_cift'
    (cifte_okey yalnızca check_winner 15-taş durumunda belirlenir)
    """
    if len(el) != 14:
        return False, ""

    if _check_yedi_cift(el, okey_tas):
        return True, "yedi_cift"

    all_tiles_t, joker_count = _build_partition_tuples(el, okey_tas)
    if _try_partition(all_tiles_t, joker_count):
        return True, "normal"
    return False, ""

def check_winner(el: list[Tas], okey_tas: Optional[Tas]) -> tuple[bool, str]:
    """
    Kazandı mı kontrol eder.
    - 14 taş: doğrudan kontrol
    - 15 taş: herhangi bir taşı atınca 14'ü geçerli mi (gerçek okey kuralı)

    Kazanma türleri:
      'normal'      → standart kazanma
      'yedi_cift'   → 7 çift yaparak
      'cifte_okey'  → sahte okeyı son taş olarak atarak kazanma (özel bonus)
    """
    if len(el) == 14:
        return _check_14_winner(el, okey_tas)
    elif len(el) == 15:
        for i in range(len(el)):
            atilan = el[i]
            el_14 = el[:i] + el[i+1:]
            won, tur = _check_14_winner(el_14, okey_tas)
            if won:
                # Atılan taş sahte okey ise → çifte okey bonusu!
                if atilan.okey:
                    return True, "cifte_okey"
                return True, tur
        return False, ""
    else:
        return False, ""

# ─── Oyun sınıfı ─────────────────────────────────────────────────────────────

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
    lobi_mesaj_id:   Optional[int]      = None
    lobi_kanal_id:   Optional[int]      = None
    izleyiciler:     list[int]          = field(default_factory=list)
    bot_oyuncular:   set[int]           = field(default_factory=set)
    el_cekti:        dict[int, bool]    = field(default_factory=dict)
    mesaj_sayaci:    int                = 0
    bot_modu:        object             = False
    diskalifiye:     set[int]           = field(default_factory=set)
    tur_sayaci:      int                = 0  # Her tur bitişinde artar, video tetiklemek için

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
        # İlk oyuncu 15 taş (okey kuralı), diğerleri 14 taş
        for i, oyuncu in enumerate(self.oyuncular):
            adet = 15 if i == 0 else 14
            self.oyuncu_elleri[oyuncu] = sort_hand(seti[:adet], self.okey_tas)
            seti = seti[adet:]
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
        self.tur_sayaci        += 1

    def talon_cek(self, user_id: int) -> Optional[Tas]:
        if not self.talon:                            return None
        if self.siradaki_oyuncu_id() != user_id:     return None
        if self.el_cekti.get(user_id):               return None
        tas = self.talon.pop(0)
        self.oyuncu_elleri[user_id].append(tas)
        self.el_cekti[user_id] = True
        return tas

    def son_tasi_al(self, user_id: int) -> Optional[Tas]:
        if not self.cop_yigi:                         return None
        if self.siradaki_oyuncu_id() != user_id:     return None
        if self.el_cekti.get(user_id):               return None
        tas = self.cop_yigi.pop()
        self.oyuncu_elleri[user_id].append(tas)
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

    def joker_at(self, user_id: int) -> tuple[bool, str]:
        """
        Sahte okey taşını at.
        Sahte okey, o elin okey taşının sabit kopyasıdır — renk/sayı kullanıcıdan ALINMAZ,
        otomatik olarak okey_tas belirlenir.
        """
        if self.siradaki_oyuncu_id() != user_id:
            return False, "Sıra sizde değil!"
        if not self.el_cekti.get(user_id):
            return False, "Önce taş çekin!"
        el = self.oyuncu_elleri.get(user_id, [])
        idx = next((i for i, t in enumerate(el) if t.okey), None)
        if idx is None:
            return False, "Elinizde sahte okey taşı yok!"
        tas = el.pop(idx)
        # Sahte okey her zaman okey_tas kimliğini taşır
        if self.okey_tas:
            tas.gorsel_renk = self.okey_tas.renk
            tas.gorsel_sayi = self.okey_tas.sayi
        self.cop_yigi.append(tas)
        self._tur_bitir(user_id)
        return True, "ok"

    def okey_tas_at(self, user_id: int,
                    gorsel_renk: Optional[str] = None,
                    gorsel_sayi: Optional[int] = None) -> tuple[bool, str]:
        """
        Gerçek okey taşını (fiziksel kart) at. Bu taş gerçek wildcard'dır.
        Oyuncu isteğe bağlı olarak hangi taşın yerine kullandığını gösterebilir.
        """
        if self.siradaki_oyuncu_id() != user_id:
            return False, "Sıra sizde değil!"
        if not self.el_cekti.get(user_id):
            return False, "Önce taş çekin!"
        if not self.okey_tas:
            return False, "Okey taşı belirlenmemiş."
        el = self.oyuncu_elleri.get(user_id, [])
        idx = next(
            (i for i, t in enumerate(el)
             if not t.okey and t.renk == self.okey_tas.renk and t.sayi == self.okey_tas.sayi),
            None
        )
        if idx is None:
            return False, "Elinizde okey taşı yok!"
        tas = el.pop(idx)
        if gorsel_renk:
            tas.gorsel_renk = gorsel_renk
        if gorsel_sayi:
            tas.gorsel_sayi = gorsel_sayi
        self.cop_yigi.append(tas)
        self._tur_bitir(user_id)
        return True, "ok"

    def peri_diz(self, user_id: int, mod: str = "renk_sayi"):
        """Eli per düzenine göre sırala ve kaydet."""
        if user_id not in self.oyuncu_elleri:
            return
        if mod == "sayi_renk":
            self.oyuncu_elleri[user_id] = sort_hand_sayi_renk(self.oyuncu_elleri[user_id])
        else:
            self.oyuncu_elleri[user_id] = sort_hand_renk_sayi(self.oyuncu_elleri[user_id])

    def okey_ac(self, user_id: int) -> tuple[bool, str]:
        if self.siradaki_oyuncu_id() != user_id:     return False, ""
        if not self.el_cekti.get(user_id):           return False, ""
        el = self.oyuncu_elleri.get(user_id, [])
        kazandi, tur = check_winner(el, self.okey_tas)
        if kazandi:
            self.durum = GameState.FINISHED
            return True, tur
        return False, ""

    def bot_hamle_yap(self, bot_id: int) -> Optional[Tas]:
        if self.siradaki_oyuncu_id() != bot_id:
            return None
        if not self.el_cekti.get(bot_id):
            if self.talon:
                self.talon_cek(bot_id)
            elif self.cop_yigi:
                self.son_tasi_al(bot_id)
            else:
                self._tur_bitir(bot_id)
                return None
        el = self.oyuncu_elleri.get(bot_id, [])
        if not el:
            self._tur_bitir(bot_id)
            return None
        kazandi, _ = check_winner(el, self.okey_tas)
        if kazandi:
            self.durum = GameState.FINISHED
            return None
        return self._bot_at_normal(bot_id)

    def _bot_at_normal(self, bot_id: int) -> Optional[Tas]:
        """Bot için en değersiz normal taşı at. Sahte okey ve gerçek okey atılmaz."""
        el = self.oyuncu_elleri.get(bot_id, [])
        if not el:
            return None
        best_idx = None
        best_puan = float("inf")
        for i, t in enumerate(el):
            if t.okey:
                continue  # Sahte okey atılmaz
            if self.okey_tas and t.renk == self.okey_tas.renk and t.sayi == self.okey_tas.sayi:
                continue  # Gerçek okey atılmaz
            puan = sum(
                1 for j, d in enumerate(el)
                if i != j and not d.okey and (
                    (d.renk == t.renk and abs(d.sayi - t.sayi) <= 2) or d.sayi == t.sayi
                )
            )
            if puan < best_puan:
                best_puan = puan
                best_idx = i
        if best_idx is None:
            best_idx = 0  # Hepsi joker/okey ise ilkini at
        return self.tas_at(bot_id, best_idx)

    @property
    def doluluk(self) -> str:
        gercek = len([u for u in self.oyuncular if u > 0])
        return f"{gercek}/{self.max_oyuncu}"
