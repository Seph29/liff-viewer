#!/usr/bin/env python3
import os, sys
import json
import tkinter as tk
from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image

from .themes import THEMES
from .liff_codec import decoder_liff_vers_rgba, encoder_fichier_image_vers_liff

APP_NAME = "liff-viewer"

def get_config_dir(app_name: str = APP_NAME) -> Path:
    if os.name == "nt":  # Windows
        base = Path(os.getenv("APPDATA") or os.getenv("LOCALAPPDATA") or Path.home() / "AppData" / "Roaming")
        return base / app_name
    elif sys.platform == "darwin":  # macOS
        return Path.home() / "Library" / "Application Support" / app_name
    else:  # Linux & autres Unix
        base = Path(os.getenv("XDG_CONFIG_HOME") or Path.home() / ".config")
        return base / app_name

CONFIG_DIR = get_config_dir()
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = CONFIG_DIR / "config.json"

def resource_path(rel: str) -> str:
    base = getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1])  # repo root en dev, _MEIPASS en binaire
    return str(Path(base) / rel)


class Theme:
    pass

def appliquer_theme(nom_theme: str):
    fallback = list(THEMES.keys())[0]
    theme_selectionne = THEMES.get(nom_theme, THEMES[fallback])
    for key, value in theme_selectionne.items():
        setattr(Theme, key, value)


class ApplicationVisionneuseLIFF:
    def __init__(self):
        self.racine = None
        self.theme_actuel = list(THEMES.keys())[0]
        self.config_data = {}
        self.dernier_dossier = ""

        self.fichiers = []
        self.index = 0
        self.image_ctk_actuelle = None
        self.image_pil_actuelle = None
        self.chemin_courant = None         
        self.taille_originale = None
        self.mode_zoom = False

    def charger_config(self):
        self.config_data = {}
        self.theme_actuel = list(THEMES.keys())[0]
        self.dernier_dossier = ""

        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.config_data = json.load(f)
                self.theme_actuel = self.config_data.get("theme", self.theme_actuel)
                self.dernier_dossier = self.config_data.get("liff_viewer_last_dir", "")
            except Exception:
                self.config_data = {}

    def sauvegarder_config(self):
        cfg = dict(self.config_data)
        cfg["theme"] = self.theme_actuel
        cfg["liff_viewer_last_dir"] = self.dernier_dossier
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4)
            self.config_data = cfg
        except Exception:
            pass

    def mettre_a_jour_theme_application(self):
        appliquer_theme(self.theme_actuel)

        self.racine.configure(fg_color=Theme.BACKGROUND)

        self.cadre_haut.configure(fg_color="transparent")
        self.label_titre.configure(text_color=Theme.TEXT_PRIMARY)
        self.label_theme.configure(text_color=Theme.TEXT_SECONDARY)
        self.menu_theme.configure(
            fg_color=Theme.CARD,
            button_color=Theme.BORDER,
            text_color=Theme.TEXT_PRIMARY,
            dropdown_fg_color=Theme.CARD,
            dropdown_text_color=Theme.DROPDOWN_TEXT,
            dropdown_hover_color=Theme.DROPDOWN_HOVER,
        )

        self.cadre_principal.configure(fg_color=Theme.SURFACE)
        self.cadre_image.configure(fg_color=Theme.SURFACE)
        self.label_image.configure(text_color=Theme.TEXT_SECONDARY)
        self.cadre_bas.configure(fg_color="transparent")
        
        boutons = [
            self.bouton_dossier,
            self.bouton_fichier,
            self.bouton_encoder_fichier,
            self.bouton_encoder_dossier,
            self.bouton_sauver_png,
            self.bouton_precedent,
            self.bouton_suivant
        ]
        
        for bouton in boutons:
            bouton.configure(
                fg_color=Theme.PRIMARY,
                hover_color=Theme.PRIMARY_DARK,
                text_color=Theme.TEXT_PRIMARY,
                font=ctk.CTkFont(weight="bold")
            )

        self.label_info_fichier.configure(text_color=Theme.TEXT_SECONDARY)

    def changer_theme(self, nouveau_theme: str):
        self.theme_actuel = nouveau_theme
        self.mettre_a_jour_theme_application()
        self.sauvegarder_config()

    def creer_interface(self):
        ctk.set_appearance_mode("dark")
        self.racine = ctk.CTk()
        self.racine.title("liff-viewer")
        try:
            if os.name == "nt":
                self.racine.iconbitmap(resource_path("ico/app.ico"))
            else:
                self.racine.iconphoto(True, tk.PhotoImage(file=resource_path("ico/app.png")))
        except Exception:
            pass
        self.racine.geometry("1000x700")
        self.racine.minsize(980, 500)

        self.racine.grid_columnconfigure(0, weight=1)
        self.racine.grid_rowconfigure(1, weight=1)

        self._creer_cadre_haut()
        self._creer_cadre_principal()
        self._creer_cadre_bas()
        
        self.racine.bind("<Left>", lambda e: self.montrer_precedent())
        self.racine.bind("<Right>", lambda e: self.montrer_suivant())
        self.racine.bind("<Control-s>", lambda e: self.sauvegarder_png())
        self.racine.bind("<Command-s>", lambda e: self.sauvegarder_png()) 
        self.mettre_a_jour_theme_application()

    def _creer_cadre_haut(self):
        self.cadre_haut = ctk.CTkFrame(self.racine, fg_color="transparent")
        self.cadre_haut.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 10))
        self.cadre_haut.grid_columnconfigure(0, weight=1)

        self.label_titre = ctk.CTkLabel(
            self.cadre_haut,
            text="Visionneuse LIFF pour FLAM",
            font=ctk.CTkFont(size=24, weight="bold"),
        )
        self.label_titre.grid(row=0, column=0, sticky="w")

        cadre_theme_droite = ctk.CTkFrame(self.cadre_haut, fg_color="transparent")
        cadre_theme_droite.grid(row=0, column=1, sticky="e")
        
        self.label_theme = ctk.CTkLabel(
            cadre_theme_droite, text="Thème :", font=ctk.CTkFont(size=12)
        )
        self.label_theme.pack(side="left", padx=(0, 5))

        self.menu_theme = ctk.CTkOptionMenu(
            cadre_theme_droite,
            values=list(THEMES.keys()),
            command=self.changer_theme,
        )
        self.menu_theme.set(self.theme_actuel)
        self.menu_theme.pack(side="left")

    def _creer_cadre_principal(self):
        self.cadre_principal = ctk.CTkFrame(
            self.racine, fg_color=Theme.SURFACE, corner_radius=10
        )
        self.cadre_principal.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 10))
        self.cadre_principal.grid_rowconfigure(0, weight=1)
        self.cadre_principal.grid_columnconfigure(0, weight=1)

        self.cadre_image = ctk.CTkFrame(self.cadre_principal, fg_color=Theme.SURFACE)
        self.cadre_image.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        self.cadre_image.grid_rowconfigure(0, weight=1)
        self.cadre_image.grid_columnconfigure(0, weight=1)

        self.label_image = ctk.CTkLabel(
            self.cadre_image,
            text="Choisissez un dossier ou un fichier .lif",
            anchor="center",
        )
        self.label_image.grid(row=0, column=0, sticky="nsew")
        self.label_image.bind("<Button-1>", lambda e: self.basculer_zoom())

    def _creer_cadre_bas(self):
        self.cadre_bas = ctk.CTkFrame(self.racine, fg_color="transparent")
        self.cadre_bas.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 15))
        self.cadre_bas.grid_columnconfigure(2, weight=1)

        boutons_gauche = ctk.CTkFrame(self.cadre_bas, fg_color="transparent")
        boutons_gauche.grid(row=0, column=0, sticky="w")

        self.bouton_dossier = ctk.CTkButton(
            boutons_gauche, text="Choisir un dossier",
            command=self.choisir_dossier, width=160
        )
        self.bouton_dossier.pack(side="left", padx=(0, 10))

        self.bouton_fichier = ctk.CTkButton(
            boutons_gauche, text="Choisir un fichier",
            command=self.choisir_fichier, width=160
        )
        self.bouton_fichier.pack(side="left", padx=(0, 10))

        self.bouton_encoder_fichier = ctk.CTkButton(
            boutons_gauche, text="Encoder fichier .lif",
            command=self.encoder_fichier, width=160
        )
        self.bouton_encoder_fichier.pack(side="left", padx=(0, 10))

        self.bouton_encoder_dossier = ctk.CTkButton(
            boutons_gauche, text="Encoder dossier .lif",
            command=self.encoder_dossier, width=160
        )
        self.bouton_encoder_dossier.pack(side="left")
        self.bouton_sauver_png = ctk.CTkButton(
            boutons_gauche, text="Sauver en PNG",
            command=self.sauvegarder_png, width=160
        )
        self.bouton_sauver_png.pack(side="left", padx=(10, 0))
        
        cadre_navigation = ctk.CTkFrame(self.cadre_bas, fg_color="transparent")
        cadre_navigation.grid(row=0, column=2, sticky="e")

        self.bouton_precedent = ctk.CTkButton(
            cadre_navigation, text="◀", width=40, command=self.montrer_precedent
        )
        self.bouton_precedent.pack(side="left", padx=(0, 5))

        self.bouton_suivant = ctk.CTkButton(
            cadre_navigation, text="▶", width=40, command=self.montrer_suivant
        )
        self.bouton_suivant.pack(side="left", padx=(5, 0))

        self.label_info_fichier = ctk.CTkLabel(self.cadre_bas, text="", anchor="e")
        self.label_info_fichier.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(5, 0))

    def choisir_dossier(self):
        dossier_initial = (
            self.dernier_dossier 
            if self.dernier_dossier and os.path.isdir(self.dernier_dossier) 
            else None
        )
        dossier = filedialog.askdirectory(initialdir=dossier_initial)
        if not dossier:
            return
        self.dernier_dossier = dossier
        self.sauvegarder_config()
        self.charger_dossier(Path(dossier))

    def choisir_fichier(self):
        dossier_initial = (
            self.dernier_dossier 
            if self.dernier_dossier and os.path.isdir(self.dernier_dossier) 
            else None
        )
        chemin = filedialog.askopenfilename(
            initialdir=dossier_initial,
            filetypes=[
                ("Images LIFF/PNG/JPG", "*.lif *.png *.jpg *.jpeg"),
                ("Tous les fichiers", "*.*"),
            ],
        )
        if not chemin:
            return
        p = Path(chemin)
        self.dernier_dossier = str(p.parent)
        self.sauvegarder_config()
        self.fichiers = [p]
        self.index = 0
        self.montrer_actuel()

    def charger_dossier(self, dossier: Path):
        if not dossier.is_dir():
            messagebox.showerror("Erreur", "Ce chemin n'est pas un dossier.")
            return

        exts = {".lif", ".png", ".jpg", ".jpeg"}
        fichiers = [
            p for p in dossier.iterdir() 
            if p.is_file() and p.suffix.lower() in exts
        ]
        fichiers.sort(key=lambda p: p.name.lower())

        if not fichiers:
            self.fichiers = []
            self.index = 0
            self.label_image.configure(
                text="Aucun fichier .lif / .png trouvé dans ce dossier."
            )
            self.label_info_fichier.configure(text="")
            return

        self.fichiers = fichiers
        self.index = 0
        self.montrer_actuel()

    def encoder_fichier(self):
        dossier_initial = (
            self.dernier_dossier 
            if self.dernier_dossier and os.path.isdir(self.dernier_dossier) 
            else None
        )
        chemin = filedialog.askopenfilename(
            initialdir=dossier_initial,
            title="Choisir une image à encoder en .lif",
            filetypes=[
                ("Images PNG/JPG", "*.png *.jpg *.jpeg"),
                ("Tous les fichiers", "*.*"),
            ],
        )
        if not chemin:
            return
        
        src = Path(chemin)
        dst = src.with_suffix(".lif")
        
        try:
            encoder_fichier_image_vers_liff(src, dst)
        except Exception as e:
            messagebox.showerror(
                "Erreur d'encodage", 
                f"Impossible d'encoder {src.name} : {e}"
            )
            return
        
        messagebox.showinfo("Encodage terminé", f"Fichier encodé :\n{dst}")

    def encoder_dossier(self):
        dossier_initial = (
            self.dernier_dossier 
            if self.dernier_dossier and os.path.isdir(self.dernier_dossier) 
            else None
        )
        dossier = filedialog.askdirectory(
            initialdir=dossier_initial,
            title="Choisir un dossier à encoder en .lif",
        )
        if not dossier:
            return
        
        chemin_dossier = Path(dossier)
        exts = {".png", ".jpg", ".jpeg"}
        count = 0
        erreurs = []

        for p in chemin_dossier.iterdir():
            if p.is_file() and p.suffix.lower() in exts:
                dst = p.with_suffix(".lif")
                try:
                    encoder_fichier_image_vers_liff(p, dst)
                    count += 1
                except Exception as e:
                    erreurs.append(f"{p.name} : {e}")

        msg = f"{count} fichier(s) encodé(s) en .lif dans\n{chemin_dossier}"
        if erreurs:
            msg += "\n\nCertains fichiers ont échoué :\n" + "\n".join(erreurs[:10])
        messagebox.showinfo("Encodage dossier", msg)

    def sauvegarder_png(self):
        if self.image_pil_actuelle is None:
            messagebox.showinfo("Rien à sauvegarder", "Ouvrez d'abord un .lif ou une image.")
            return

        dossier_initial = (
            self.dernier_dossier
            if self.dernier_dossier and os.path.isdir(self.dernier_dossier)
            else None
        )
        stem = Path(self.chemin_courant).stem if self.chemin_courant else "image"
        cible = filedialog.asksaveasfilename(
            initialdir=dossier_initial,
            initialfile=f"{stem}.png",
            defaultextension=".png",
            filetypes=[("PNG", "*.png")],
            title="Enregistrer l'image en PNG",
        )
        if not cible:
            return

        try:
            img = self.image_pil_actuelle
            # Assure-toi d'un mode compatible PNG (gère l'alpha si présent)
            if img.mode not in ("RGB", "RGBA"):
                # conserver l'alpha si disponible
                img = img.convert("RGBA" if "A" in img.getbands() else "RGB")

            img.save(cible, format="PNG")
            # mémorise le dossier pour la prochaine fois
            self.dernier_dossier = str(Path(cible).parent)
            self.sauvegarder_config()
            messagebox.showinfo("Sauvegardé", f"Image sauvegardée :\n{cible}")
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de sauvegarder en PNG : {e}")

    
    def montrer_actuel(self):
        if not self.fichiers:
            return

        chemin = self.fichiers[self.index]
        
        try:
            if chemin.suffix.lower() == ".lif":
                w, h, rgba = decoder_liff_vers_rgba(chemin)
                img = Image.frombytes("RGBA", (w, h), rgba)
            else:
                img = Image.open(chemin).convert("RGBA")
                w, h = img.size
        except Exception as e:
            self.label_image.configure(text=f"Erreur de décodage : {e}")
            self.label_info_fichier.configure(
                text=f"{self.index + 1}/{len(self.fichiers)} - {chemin.name}"
            )
            self.image_ctk_actuelle = None
            return

        self.taille_originale = (w, h)
        self.image_pil_actuelle = img
        self.chemin_courant = chemin
        
        est_icone = max(w, h) <= 64
        max_dim = 512

        if est_icone and not self.mode_zoom:
            nouvelle_taille = (w, h)
        else:
            scale = max(1, min(max_dim // max(1, w), max_dim // max(1, h)))
            nouvelle_taille = (max(1, w * scale), max(1, h * scale))

        img_redimensionnee = img.resize(nouvelle_taille, Image.NEAREST)

        self.image_ctk_actuelle = ctk.CTkImage(
            light_image=img_redimensionnee,
            dark_image=img_redimensionnee,
            size=nouvelle_taille,
        )

        self.label_image.configure(image=self.image_ctk_actuelle, text="")
        self.label_info_fichier.configure(
            text=f"{self.index + 1}/{len(self.fichiers)}  •  {chemin.name}  •  {w}x{h}"
        )

    def basculer_zoom(self):
        self.mode_zoom = not self.mode_zoom
        self.montrer_actuel()

    def montrer_suivant(self):
        if not self.fichiers:
            return
        self.index = (self.index + 1) % len(self.fichiers)
        self.montrer_actuel()

    def montrer_precedent(self):
        if not self.fichiers:
            return
        self.index = (self.index - 1) % len(self.fichiers)
        self.montrer_actuel()

    def executer(self):
        self.charger_config()
        appliquer_theme(self.theme_actuel)
        self.creer_interface()
        self.racine.mainloop()


def main():
    app = ApplicationVisionneuseLIFF()
    app.executer()


if __name__ == "__main__":
    main()