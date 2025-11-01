import os, csv, math, time, sys
from datetime import datetime, UTC
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from ttkthemes import ThemedTk
from PIL import ImageGrab, Image, ImageTk

# plotting
try:
    import matplotlib.pyplot as plt
    PLOT_OK = True
except Exception:
    PLOT_OK = False

# constants
EMISSION_CSV = 'emission_factors_extended.csv'
AIRPORTS_CSV = 'airports_extended.csv'
HISTORY_CSV = 'history.csv'
BADGE_SVG = 'badge.svg'
RF_MULTIPLIER = 1.9
OFFSET_COST_PER_KG = 0.60
SAF_MAX_REDUCTION_PERCENT = 0.80
CO2_TO_FUEL_FACTOR = 3.16
FUEL_DENSITY_KG_LITER = 0.8
SHORT_HAUL_MAX_KM = 1500
SHORT_HAUL_LTO_CO2_FIXED_KG = 50.0
LONG_HAUL_LTO_CO2_FIXED_KG = 150.0

# Modern Color Palette
COLORS = {
    'bg_primary': '#0a1628',
    'bg_secondary': '#0f1f3a',
    'bg_card': '#1a2942',
    'bg_card_hover': '#253754',
    'accent_green': '#00ff88',
    'accent_green_dark': '#00cc6a',
    'accent_blue': '#0088ff',
    'text_primary': '#e8f4f8',
    'text_secondary': '#a8c5d1',
    'text_muted': '#6b8ca3',
    'border': '#2d4663',
    'error': '#ff4466',
    'warning': '#ffaa00',
    'success': '#00ff88'
}

# ---------- helpers ----------
def load_csv_factors(path=EMISSION_CSV):
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} missing. Save emission_factors_extended.csv here.")
    d = {}
    with open(path, newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                d[row['AircraftType']] = float(row['EmissionFactor_kgCO2perkm'])
            except:
                pass
    return d

def load_airports(path=AIRPORTS_CSV):
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} missing. Save airports_extended.csv here.")
    out = {}
    with open(path, newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            iata = row['IATA'].strip().upper()
            try:
                lat = float(row['Latitude']); lon = float(row['Longitude'])
            except:
                continue
            out[iata] = {'name': row.get('Name',''), 'lat': lat, 'lon': lon, 'country': row.get('Country','')}
    return out

def haversine_km(lat1,lon1,lat2,lon2):
    R=6371.0
    phi1 = math.radians(lat1); phi2 = math.radians(lat2)
    dphi = math.radians(lat2-lat1); dlambda = math.radians(lon2-lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2*math.atan2(math.sqrt(a), math.sqrt(1-a)); return R*c

def estimate_co2(distance_km, base_factor, rf=False):
    fixed = SHORT_HAUL_LTO_CO2_FIXED_KG if distance_km <= SHORT_HAUL_MAX_KM else LONG_HAUL_LTO_CO2_FIXED_KG
    total = distance_km * base_factor + fixed
    if rf:
        total *= RF_MULTIPLIER
    return total

def fuel_liters_from_co2(co2_kg):
    fuel_kg = co2_kg / CO2_TO_FUEL_FACTOR
    return fuel_kg / FUEL_DENSITY_KG_LITER

def trees_needed(co2):
    return co2 / 22.0

def log_history_row(row, path=HISTORY_CSV):
    header = ['timestamp','origin','destination','distance_km','aircraft','rf','saf_pct','co2_kg','fuel_liters','trees','offset_inr']
    exists = os.path.exists(path)
    with open(path,'a',newline='',encoding='utf-8') as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(header)
        w.writerow(row)

# ---------- Modern Components ----------
class ModernCard(tk.Frame):
    """A modern card component with subtle shadows and rounded corners"""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=COLORS['bg_card'], **kwargs)
        self.configure(highlightthickness=1, highlightbackground=COLORS['border'])
        
class ModernButton(tk.Button):
    """A modern button with hover effects"""
    def __init__(self, parent, style='primary', **kwargs):
        # Extract bg/fg from kwargs if provided
        custom_bg = kwargs.pop('bg', None)
        custom_fg = kwargs.pop('fg', None)
        
        if style == 'primary':
            bg = COLORS['accent_green']
            fg = COLORS['bg_primary']
            hover_bg = COLORS['accent_green_dark']
        elif style == 'secondary':
            bg = COLORS['bg_card_hover']
            fg = COLORS['text_primary']
            hover_bg = COLORS['border']
        else:
            bg = custom_bg or COLORS['bg_card']
            fg = custom_fg or COLORS['text_primary']
            hover_bg = COLORS['bg_card_hover']
        
        # Override with custom colors if provided
        if custom_bg:
            bg = custom_bg
        if custom_fg:
            fg = custom_fg
        
        super().__init__(parent, bg=bg, fg=fg, relief='flat', 
                        font=('Segoe UI', 10, 'bold'),
                        cursor='hand2',
                        activebackground=hover_bg,
                        activeforeground=fg,
                        **kwargs)
        
        self.default_bg = bg
        self.hover_bg = hover_bg
        
        self.bind('<Enter>', lambda e: self.configure(bg=self.hover_bg))
        self.bind('<Leave>', lambda e: self.configure(bg=self.default_bg))

class ModernEntry(tk.Entry):
    """A modern entry field"""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, 
                        bg=COLORS['bg_secondary'],
                        fg=COLORS['text_primary'],
                        insertbackground=COLORS['accent_green'],
                        relief='flat',
                        font=('Segoe UI', 10),
                        highlightthickness=1,
                        highlightcolor=COLORS['accent_green'],
                        highlightbackground=COLORS['border'],
                        **kwargs)

class ModernTooltip:
    """Modern tooltip with animations"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)
        
    def show(self, e=None):
        if self.tip: return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        self.tip.configure(bg=COLORS['bg_card'])
        
        frame = tk.Frame(self.tip, bg=COLORS['bg_card'], 
                        highlightthickness=1, 
                        highlightbackground=COLORS['accent_green'])
        frame.pack()
        
        lbl = tk.Label(frame, text=self.text, 
                      bg=COLORS['bg_card'], 
                      fg=COLORS['text_primary'],
                      font=('Segoe UI', 9),
                      padx=12, pady=6)
        lbl.pack()
        
    def hide(self, e=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None

# ---------- modal ----------
def show_modern_modal(master, title, message, type='info'):
    modal = tk.Toplevel(master)
    modal.transient(master)
    modal.title(title)
    modal.geometry("450x200")
    modal.configure(bg=COLORS['bg_primary'])
    
    # Icon based on type
    icon_map = {'info': 'ℹ️', 'error': '⚠️', 'success': '✓'}
    icon = icon_map.get(type, 'ℹ️')
    
    tk.Label(modal, text=icon, bg=COLORS['bg_primary'], 
            fg=COLORS['accent_green'], font=('Segoe UI', 32)).pack(pady=(20,10))
    
    tk.Label(modal, text=title, fg=COLORS['text_primary'], 
            bg=COLORS['bg_primary'], 
            font=('Segoe UI', 14, 'bold')).pack(pady=(0,10))
    
    tk.Label(modal, text=message, fg=COLORS['text_secondary'], 
            bg=COLORS['bg_primary'], 
            wraplength=400, justify='center').pack(padx=20)
    
    ModernButton(modal, text="OK", command=modal.destroy, 
                style='primary').pack(pady=20, ipadx=20)
    
    modal.grab_set()
    modal.wait_window()

# ---------- UI app ----------
class GreenSkiesUltra:
    def __init__(self, root):
        self.root = root
        root.title("GreenSkies Ultra – Flight Emissions Calculator")
        root.configure(bg=COLORS['bg_primary'])
        root.geometry("1200x800")
        root.minsize(1000,700)

        # load data
        self.factors = load_csv_factors()
        self.airports = load_airports()
        self.airport_options = [f"{k} – {v['name']}, {v['country']}" for k,v in self.airports.items()]

        # Custom styles
        self._setup_styles()
        
        # main layout
        self._create_header()
        self._create_navigation()
        self._create_content_area()
        self.show_home()

        # keyboard shortcuts
        root.bind("<Control-s>", lambda e: self.screenshot_window())
        root.bind("<Control-e>", lambda e: self.export_history())

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        # Combobox
        style.configure('Modern.TCombobox',
                       fieldbackground=COLORS['bg_secondary'],
                       background=COLORS['bg_card'],
                       foreground=COLORS['text_primary'],
                       arrowcolor=COLORS['accent_green'],
                       bordercolor=COLORS['border'])
        
        # Checkbutton
        style.configure('Modern.TCheckbutton',
                       background=COLORS['bg_card'],
                       foreground=COLORS['text_primary'])
        
        # Scale
        style.configure('Modern.Horizontal.TScale',
                       background=COLORS['bg_card'],
                       troughcolor=COLORS['bg_secondary'],
                       bordercolor=COLORS['border'])
        
        # Treeview
        style.configure('Modern.Treeview',
                       background=COLORS['bg_secondary'],
                       foreground=COLORS['text_primary'],
                       fieldbackground=COLORS['bg_secondary'],
                       borderwidth=0)
        style.configure('Modern.Treeview.Heading',
                       background=COLORS['bg_card'],
                       foreground=COLORS['text_primary'],
                       borderwidth=1,
                       relief='flat')
        style.map('Modern.Treeview',
                 background=[('selected', COLORS['accent_blue'])])

    # ----- header -----
    def _create_header(self):
        header = tk.Frame(self.root, bg=COLORS['bg_secondary'], height=80)
        header.pack(side="top", fill="x")
        header.pack_propagate(False)
        
        # Left: Logo and title
        left = tk.Frame(header, bg=COLORS['bg_secondary'])
        left.pack(side="left", padx=30, pady=15)
        
        tk.Label(left, text="✈", bg=COLORS['bg_secondary'], 
                fg=COLORS['accent_green'], 
                font=('Segoe UI', 28, 'bold')).pack(side="left", padx=(0,15))
        
        title_frame = tk.Frame(left, bg=COLORS['bg_secondary'])
        title_frame.pack(side="left")
        
        tk.Label(title_frame, text="GreenSkies Ultra", 
                bg=COLORS['bg_secondary'], 
                fg=COLORS['text_primary'],
                font=('Segoe UI', 18, 'bold')).pack(anchor='w')
        
        tk.Label(title_frame, text="Flight Emissions Calculator", 
                bg=COLORS['bg_secondary'], 
                fg=COLORS['text_muted'],
                font=('Segoe UI', 10)).pack(anchor='w')
        
        # Right: Actions
        right = tk.Frame(header, bg=COLORS['bg_secondary'])
        right.pack(side="right", padx=30)
        
        btn_screenshot = ModernButton(right, text="📸 Screenshot", 
                                     style='secondary',
                                     command=self.screenshot_window)
        btn_screenshot.pack(side="right", padx=5)
        ModernTooltip(btn_screenshot, "Save window as PNG (Ctrl+S)")

    # ----- navigation -----
    def _create_navigation(self):
        nav = tk.Frame(self.root, bg=COLORS['bg_secondary'], width=220)
        nav.pack(side="left", fill="y")
        nav.pack_propagate(False)
        
        # Menu title
        tk.Label(nav, text="NAVIGATION", 
                bg=COLORS['bg_secondary'], 
                fg=COLORS['text_muted'],
                font=('Segoe UI', 9, 'bold')).pack(pady=(25,15), padx=20, anchor='w')
        
        # Navigation buttons
        nav_items = [
            ("🏠  Home", self.show_home),
            ("📊  History", self.show_history),
            ("ℹ️  About", self.show_about)
        ]
        
        self.nav_buttons = []
        for text, command in nav_items:
            btn = tk.Button(nav, text=text, 
                          bg=COLORS['bg_secondary'],
                          fg=COLORS['text_secondary'],
                          relief='flat',
                          font=('Segoe UI', 11),
                          cursor='hand2',
                          anchor='w',
                          padx=20,
                          pady=12,
                          command=command)
            btn.pack(fill='x', padx=10, pady=2)
            self.nav_buttons.append(btn)
            
            # Hover effect
            btn.bind('<Enter>', lambda e, b=btn: b.configure(
                bg=COLORS['bg_card'], fg=COLORS['text_primary']))
            btn.bind('<Leave>', lambda e, b=btn: b.configure(
                bg=COLORS['bg_secondary'], fg=COLORS['text_secondary']))
        
        # Set home as active
        self.set_active_nav(0)

    def set_active_nav(self, index):
        """Highlight active navigation button"""
        for i, btn in enumerate(self.nav_buttons):
            if i == index:
                btn.configure(bg=COLORS['bg_card'], 
                            fg=COLORS['accent_green'],
                            relief='flat')
            else:
                btn.configure(bg=COLORS['bg_secondary'], 
                            fg=COLORS['text_secondary'])

    # ----- content area -----
    def _create_content_area(self):
        self.content = tk.Frame(self.root, bg=COLORS['bg_primary'])
        self.content.pack(side="left", fill="both", expand=True, padx=20, pady=20)

        # Create frames
        self.home_frame = tk.Frame(self.content, bg=COLORS['bg_primary'])
        self.history_frame = tk.Frame(self.content, bg=COLORS['bg_primary'])
        self.about_frame = tk.Frame(self.content, bg=COLORS['bg_primary'])

        # Build UIs
        self._build_home(self.home_frame)
        self._build_history(self.history_frame)
        self._build_about(self.about_frame)

    # ----- Home UI -----
    def _build_home(self, parent):
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_columnconfigure(1, weight=1)

        # Left: Input Card
        card_input = ModernCard(parent)
        card_input.grid(row=0, column=0, sticky="nsew", padx=(0,10), pady=0)
        
        # Card header
        header = tk.Frame(card_input, bg=COLORS['bg_card'])
        header.pack(fill='x', padx=20, pady=(20,10))
        tk.Label(header, text="Flight Details", 
                bg=COLORS['bg_card'], 
                fg=COLORS['text_primary'],
                font=('Segoe UI', 14, 'bold')).pack(anchor='w')
        
        # Content
        content = tk.Frame(card_input, bg=COLORS['bg_card'])
        content.pack(fill='both', expand=True, padx=20, pady=(0,20))
        
        # Variables
        self.origin_var = tk.StringVar()
        self.dest_var = tk.StringVar()
        self.dist_var = tk.StringVar()
        self.ac_var = tk.StringVar()
        self.rf_var = tk.BooleanVar(value=False)
        self.saf_var = tk.IntVar(value=0)
        
        # Origin
        tk.Label(content, text="Origin Airport", 
                bg=COLORS['bg_card'], 
                fg=COLORS['text_secondary'],
                font=('Segoe UI', 10)).pack(anchor='w', pady=(10,5))
        
        self.origin_cb = ttk.Combobox(content, values=self.airport_options, 
                                     textvariable=self.origin_var,
                                     style='Modern.TCombobox',
                                     font=('Segoe UI', 10))
        self.origin_cb.pack(fill='x', pady=(0,5))
        ModernTooltip(self.origin_cb, "Enter IATA code (e.g., DEL) or search by airport name")
        
        # Destination
        tk.Label(content, text="Destination Airport", 
                bg=COLORS['bg_card'], 
                fg=COLORS['text_secondary'],
                font=('Segoe UI', 10)).pack(anchor='w', pady=(15,5))
        
        self.dest_cb = ttk.Combobox(content, values=self.airport_options, 
                                   textvariable=self.dest_var,
                                   style='Modern.TCombobox',
                                   font=('Segoe UI', 10))
        self.dest_cb.pack(fill='x', pady=(0,5))
        
        # Distance
        tk.Label(content, text="Or Manual Distance (km)", 
                bg=COLORS['bg_card'], 
                fg=COLORS['text_secondary'],
                font=('Segoe UI', 10)).pack(anchor='w', pady=(15,5))
        
        dist_entry = ModernEntry(content, textvariable=self.dist_var)
        dist_entry.pack(fill='x')
        
        # Aircraft
        tk.Label(content, text="Aircraft Type", 
                bg=COLORS['bg_card'], 
                fg=COLORS['text_secondary'],
                font=('Segoe UI', 10)).pack(anchor='w', pady=(15,5))
        
        self.ac_cb = ttk.Combobox(content, values=list(self.factors.keys()),
                                 textvariable=self.ac_var,
                                 style='Modern.TCombobox',
                                 font=('Segoe UI', 10))
        self.ac_cb.pack(fill='x')
        if self.factors:
            self.ac_cb.current(0)
        
        # SAF Slider
        saf_frame = tk.Frame(content, bg=COLORS['bg_card'])
        saf_frame.pack(fill='x', pady=(20,5))
        
        saf_label_frame = tk.Frame(saf_frame, bg=COLORS['bg_card'])
        saf_label_frame.pack(fill='x')
        
        tk.Label(saf_label_frame, text="Sustainable Aviation Fuel (SAF)", 
                bg=COLORS['bg_card'], 
                fg=COLORS['text_secondary'],
                font=('Segoe UI', 10)).pack(side='left')
        
        self.saf_value_lbl = tk.Label(saf_label_frame, text="0%", 
                                     bg=COLORS['bg_card'], 
                                     fg=COLORS['accent_green'],
                                     font=('Segoe UI', 10, 'bold'))
        self.saf_value_lbl.pack(side='right')
        
        saf_scale = ttk.Scale(saf_frame, from_=0, to=50, orient='horizontal',
                            variable=self.saf_var,
                            style='Modern.Horizontal.TScale',
                            command=lambda e: self.saf_value_lbl.config(
                                text=f"{self.saf_var.get():.0f}%"))
        saf_scale.pack(fill='x', pady=(5,0))
        ModernTooltip(saf_scale, "SAF blend percentage reduces CO₂ emissions proportionally")
        
        # RF Checkbox
        rf_check = ttk.Checkbutton(content, text="Apply Radiative Forcing (1.9x)",
                                  variable=self.rf_var,
                                  style='Modern.TCheckbutton')
        rf_check.pack(anchor='w', pady=(15,0))
        ModernTooltip(rf_check, "Account for non-CO₂ warming effects at cruise altitude")
        
        # Action Buttons
        btn_frame = tk.Frame(content, bg=COLORS['bg_card'])
        btn_frame.pack(fill='x', pady=(25,0))
        
        ModernButton(btn_frame, text="Calculate Emissions", 
                    command=self.calculate_action,
                    style='primary').pack(side='left', padx=(0,10), ipadx=15, ipady=8)
        
        ModernButton(btn_frame, text="Compare Aircraft", 
                    command=self.compare_action,
                    style='secondary').pack(side='left', padx=(0,10), ipadx=15, ipady=8)
        
        reset_btn = ModernButton(btn_frame, text="Reset", 
                    command=self.reset_home,
                    style='custom')
        reset_btn.configure(bg=COLORS['bg_secondary'], fg=COLORS['text_secondary'])
        reset_btn.default_bg = COLORS['bg_secondary']
        reset_btn.hover_bg = COLORS['bg_card_hover']
        reset_btn.pack(side='left', ipadx=15, ipady=8)

        # Right: Results Card
        card_results = ModernCard(parent)
        card_results.grid(row=0, column=1, sticky='nsew', padx=(10,0), pady=0)
        
        # Card header
        header = tk.Frame(card_results, bg=COLORS['bg_card'])
        header.pack(fill='x', padx=20, pady=(20,10))
        tk.Label(header, text="Emission Results", 
                bg=COLORS['bg_card'], 
                fg=COLORS['text_primary'],
                font=('Segoe UI', 14, 'bold')).pack(anchor='w')
        
        # Scrollable content frame
        canvas = tk.Canvas(card_results, bg=COLORS['bg_card'], 
                          highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(card_results, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=COLORS['bg_card'])
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Results content in scrollable frame
        res_content = tk.Frame(scrollable_frame, bg=COLORS['bg_card'])
        res_content.pack(fill='both', expand=True, padx=20, pady=(0,20))
        
        # Result metrics
        metrics = [
            ("Distance", "— km", "📏"),
            ("CO₂ Emissions", "— kg", "💨"),
            ("Fuel Burn", "— liters", "⛽"),
            ("Trees Needed", "—", "🌳"),
            ("Offset Cost", "— ₹", "💰")
        ]
        
        self.result_labels = {}
        for i, (label, default, icon) in enumerate(metrics):
            metric_frame = tk.Frame(res_content, bg=COLORS['bg_secondary'],
                                   highlightthickness=1,
                                   highlightbackground=COLORS['border'])
            metric_frame.pack(fill='x', pady=8)
            
            top_row = tk.Frame(metric_frame, bg=COLORS['bg_secondary'])
            top_row.pack(fill='x', padx=15, pady=(12,5))
            
            tk.Label(top_row, text=icon, bg=COLORS['bg_secondary'],
                    font=('Segoe UI', 16)).pack(side='left', padx=(0,10))
            
            tk.Label(top_row, text=label, bg=COLORS['bg_secondary'],
                    fg=COLORS['text_muted'],
                    font=('Segoe UI', 9)).pack(side='left')
            
            value_lbl = tk.Label(metric_frame, text=default,
                                bg=COLORS['bg_secondary'],
                                fg=COLORS['accent_green'],
                                font=('Segoe UI', 16, 'bold'))
            value_lbl.pack(anchor='w', padx=15, pady=(0,12))
            
            self.result_labels[label] = value_lbl
        
        # Suggestion box
        suggestion_frame = tk.Frame(res_content, bg=COLORS['accent_blue'],
                                   highlightthickness=1,
                                   highlightbackground=COLORS['accent_blue'])
        suggestion_frame.pack(fill='x', pady=(15,0))
        
        tk.Label(suggestion_frame, text="💡 Tip", 
                bg=COLORS['accent_blue'],
                fg=COLORS['bg_primary'],
                font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=15, pady=(10,5))
        
        self.suggestion_lbl = tk.Label(suggestion_frame, text="Enter flight details to see emissions and recommendations",
                                      bg=COLORS['accent_blue'],
                                      fg=COLORS['bg_primary'],
                                      font=('Segoe UI', 9),
                                      wraplength=400,
                                      justify='left')
        self.suggestion_lbl.pack(anchor='w', padx=15, pady=(0,10))
        
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Enable mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

    # ----- History UI -----
    def _build_history(self, parent):
        # Header
        header = tk.Frame(parent, bg=COLORS['bg_primary'])
        header.pack(fill='x', pady=(0,15))
        
        tk.Label(header, text="Flight History", 
                bg=COLORS['bg_primary'], 
                fg=COLORS['text_primary'],
                font=('Segoe UI', 16, 'bold')).pack(side='left')
        
        ModernButton(header, text="📥 Export CSV", 
                    command=self.export_history,
                    style='secondary').pack(side='right', padx=5)
        
        ModernButton(header, text="⬆ Load to Home", 
                    command=self.load_selected_history,
                    style='secondary').pack(side='right', padx=5)
        
        # Table card
        table_card = ModernCard(parent)
        table_card.pack(fill='both', expand=True)
        
        # Treeview
        cols = ("ts", "route", "dist_km", "aircraft", "co2_kg")
        tree = ttk.Treeview(table_card, columns=cols, show='headings',
                           selectmode='browse', style='Modern.Treeview')
        
        tree.heading("ts", text="Timestamp")
        tree.heading("route", text="Route")
        tree.heading("dist_km", text="Distance (km)")
        tree.heading("aircraft", text="Aircraft")
        tree.heading("co2_kg", text="CO₂ (kg)")
        
        tree.column("ts", width=180)
        tree.column("route", width=200)
        tree.column("dist_km", width=120)
        tree.column("aircraft", width=180)
        tree.column("co2_kg", width=120)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(table_card, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side='left', fill='both', expand=True, padx=2, pady=2)
        scrollbar.pack(side='right', fill='y')
        
        self.history_tree = tree
        self._refresh_history_tree()

    # ----- About UI -----
    def _build_about(self, parent):
        card = ModernCard(parent)
        card.pack(fill='both', expand=True, padx=50, pady=50)
        
        content = tk.Frame(card, bg=COLORS['bg_card'])
        content.pack(fill='both', expand=True, padx=40, pady=40)
        
        tk.Label(content, text="About GreenSkies Ultra", 
                bg=COLORS['bg_card'], 
                fg=COLORS['text_primary'],
                font=('Segoe UI', 20, 'bold')).pack(anchor='w', pady=(0,20))
        
        about_text = """GreenSkies Ultra is an educational flight CO₂ emissions calculator designed to raise awareness about aviation's environmental impact.

Key Features:
• Haversine distance calculation for great-circle routes
• Per-kilometer emission factors based on aircraft type
• LTO (Landing and Take-Off) cycle emissions
• Radiative Forcing multiplier (~1.9x)
• Sustainable Aviation Fuel (SAF) impact simulation
• Fuel consumption estimation
• Carbon offset cost calculation

This tool is designed for educational purposes and provides approximate emissions estimates. It is not a certified emissions calculator.

Developed for classroom projects and environmental awareness."""
        
        tk.Label(content, text=about_text, 
                bg=COLORS['bg_card'], 
                fg=COLORS['text_secondary'],
                font=('Segoe UI', 10),
                justify='left',
                wraplength=700).pack(anchor='w', pady=(0,30))
        
        # Info boxes
        info_frame = tk.Frame(content, bg=COLORS['bg_card'])
        info_frame.pack(fill='x')
        
        info_items = [
            ("✈", "Aircraft Types", f"{len(self.factors)} aircraft models"),
            ("🌍", "Airports", f"{len(self.airports)} airports worldwide"),
            ("📊", "History Logs", "CSV export available")
        ]
        
        for icon, title, desc in info_items:
            box = tk.Frame(info_frame, bg=COLORS['bg_secondary'],
                          highlightthickness=1,
                          highlightbackground=COLORS['border'])
            box.pack(side='left', padx=10, pady=10, ipadx=20, ipady=15)
            
            tk.Label(box, text=icon, bg=COLORS['bg_secondary'],
                    font=('Segoe UI', 24)).pack()
            
            tk.Label(box, text=title, bg=COLORS['bg_secondary'],
                    fg=COLORS['text_primary'],
                    font=('Segoe UI', 11, 'bold')).pack(pady=(5,2))
            
            tk.Label(box, text=desc, bg=COLORS['bg_secondary'],
                    fg=COLORS['text_muted'],
                    font=('Segoe UI', 9)).pack()

    # ----- frame switchers -----
    def clear_content(self):
        for f in (self.home_frame, self.history_frame, self.about_frame):
            f.pack_forget()
            
    def show_home(self):
        self.clear_content()
        self.home_frame.pack(fill='both', expand=True)
        self.set_active_nav(0)
        
    def show_history(self):
        self.clear_content()
        self.history_frame.pack(fill='both', expand=True)
        self.set_active_nav(1)
        self._refresh_history_tree()
        
    def show_about(self):
        self.clear_content()
        self.about_frame.pack(fill='both', expand=True)
        self.set_active_nav(2)

    # ----- logic actions -----
    def _parse_iata_from_combo(self, text):
        if not text: return ""
        if "–" in text:
            return text.split("–")[0].strip().upper()
        return text.strip().upper()

    def calculate_action(self):
        origin_text = self.origin_var.get()
        dest_text = self.dest_var.get()
        origin = self._parse_iata_from_combo(origin_text)
        dest = self._parse_iata_from_combo(dest_text)
        manual = self.dist_var.get().strip()
        
        if origin and dest:
            if origin not in self.airports or dest not in self.airports:
                show_modern_modal(self.root, "Airport Not Found",
                                f"IATA codes not found: {origin} / {dest}\nPlease select from the dropdown list.",
                                'error')
                return
            a = self.airports[origin]
            b = self.airports[dest]
            dist = haversine_km(a['lat'], a['lon'], b['lat'], b['lon'])
        else:
            try:
                dist = float(manual)
            except:
                show_modern_modal(self.root, "Input Required",
                                "Please enter valid origin & destination or a numeric distance.",
                                'error')
                return
        
        ac = self.ac_cb.get()
        if ac not in self.factors:
            show_modern_modal(self.root, "Aircraft Required",
                            "Please select a valid aircraft type.",
                            'error')
            return
        
        rf = bool(self.rf_var.get())
        saf_pct = self.saf_var.get()
        base_factor = self.factors[ac]
        co2 = estimate_co2(dist, base_factor, rf)
        
        if saf_pct > 0:
            reduction = saf_pct / 100 * SAF_MAX_REDUCTION_PERCENT
            co2 *= (1 - reduction)
        
        fuel_l = fuel_liters_from_co2(co2)
        trees = trees_needed(co2)
        cost = co2 * OFFSET_COST_PER_KG
        
        # Update UI with animation effect
        self.result_labels["Distance"].config(text=f"{dist:.1f} km")
        self.result_labels["CO₂ Emissions"].config(text=f"{co2:.1f} kg")
        self.result_labels["Fuel Burn"].config(text=f"{fuel_l:.0f} liters")
        self.result_labels["Trees Needed"].config(text=f"{trees:.1f}")
        self.result_labels["Offset Cost"].config(text=f"₹{cost:.0f}")
        
        # Suggestion based on distance
        if dist < 350:
            suggestion = "Short route detected. Consider train or bus alternatives for lower emissions."
        elif dist < 1500:
            suggestion = "Medium-haul flight. Choose direct flights and fuel-efficient aircraft when possible."
        else:
            suggestion = "Long-haul flight. Consider carbon offsets and airlines with SAF programs."
        
        self.suggestion_lbl.config(text=suggestion)
        
        # Log to history
        ts = datetime.now(UTC).isoformat()
        entry = [ts, origin, dest, f"{dist:.1f}", ac, rf, f"{saf_pct}", 
                f"{co2:.1f}", f"{fuel_l:.1f}", f"{trees:.1f}", f"{cost:.1f}"]
        log_history_row(entry)
        self._refresh_history_tree()

    def compare_action(self):
        # Create loading popup
        popup = tk.Toplevel(self.root)
        popup.geometry("400x150")
        popup.title("Comparing Aircraft")
        popup.configure(bg=COLORS['bg_primary'])
        popup.transient(self.root)
        
        tk.Label(popup, text="🔄", bg=COLORS['bg_primary'],
                fg=COLORS['accent_green'],
                font=('Segoe UI', 32)).pack(pady=(20,10))
        
        tk.Label(popup, text="Preparing comparison chart...", 
                bg=COLORS['bg_primary'], 
                fg=COLORS['text_primary'],
                font=('Segoe UI', 11)).pack()
        
        pb = ttk.Progressbar(popup, mode='indeterminate', length=350)
        pb.pack(pady=15)
        pb.start(10)
        
        self.root.update()
        
        try:
            origin = self._parse_iata_from_combo(self.origin_var.get())
            dest = self._parse_iata_from_combo(self.dest_var.get())
            
            if origin and dest and origin in self.airports and dest in self.airports:
                a = self.airports[origin]
                b = self.airports[dest]
                dist = haversine_km(a['lat'], a['lon'], b['lat'], b['lon'])
            else:
                dist = float(self.dist_var.get() or 0)
        except Exception as e:
            popup.destroy()
            show_modern_modal(self.root, "Input Required",
                            "Please enter valid route information or distance.",
                            'error')
            return
        
        rf = self.rf_var.get()
        saf_pct = self.saf_var.get()
        
        labels = []
        vals = []
        for k, v in self.factors.items():
            co2 = estimate_co2(dist, v, rf)
            if saf_pct > 0:
                co2 *= (1 - saf_pct/100 * SAF_MAX_REDUCTION_PERCENT)
            labels.append(k)
            vals.append(co2)
        
        popup.destroy()
        
        if not PLOT_OK:
            show_modern_modal(self.root, "Matplotlib Required",
                            "Please install matplotlib to view comparison charts.",
                            'error')
            return
        
        # Create modern chart
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(12, 7))
        fig.patch.set_facecolor('#0a1628')
        ax.set_facecolor('#0f1f3a')
        
        bars = ax.bar(labels, vals, color='#00ff88', edgecolor='#00cc6a', linewidth=1.5)
        
        ax.set_title(f'CO₂ Emissions Comparison for {dist:.0f} km Flight',
                    fontsize=16, fontweight='bold', color='#e8f4f8', pad=20)
        ax.set_xlabel('Aircraft Type', fontsize=12, color='#a8c5d1')
        ax.set_ylabel('CO₂ Emissions (kg)', fontsize=12, color='#a8c5d1')
        
        plt.xticks(rotation=45, ha='right', fontsize=9)
        ax.tick_params(colors='#6b8ca3')
        ax.grid(axis='y', alpha=0.2, linestyle='--', color='#2d4663')
        
        for i, v in enumerate(vals):
            ax.text(i, v + max(vals)*0.02, f'{v:.0f}', 
                   ha='center', va='bottom', fontsize=8, 
                   color='#00ff88', fontweight='bold')
        
        plt.tight_layout()
        plt.show()

    def _refresh_history_tree(self):
        if not hasattr(self, 'history_tree') or self.history_tree is None:
            return
        
        tree = self.history_tree
        for i in tree.get_children():
            tree.delete(i)
        
        if not os.path.exists(HISTORY_CSV):
            return
        
        with open(HISTORY_CSV, newline='', encoding='utf-8') as f:
            r = csv.DictReader(f)
            for row in r:
                route = f"{row['origin']} → {row['destination']}"
                tree.insert('', 'end', values=(
                    row['timestamp'], 
                    route, 
                    float(row['distance_km']), 
                    row['aircraft'], 
                    float(row['co2_kg'])
                ))

    def load_selected_history(self):
        sel = self.history_tree.selection()
        if not sel:
            show_modern_modal(self.root, "No Selection",
                            "Please select a row from the history table.",
                            'info')
            return
        
        vals = self.history_tree.item(sel[0])['values']
        route = vals[1]
        
        try:
            origin, dest = route.split(' → ')
        except:
            origin = dest = ""
        
        self.origin_var.set(origin)
        self.dest_var.set(dest)
        self.dist_var.set(str(vals[2]))
        self.ac_cb.set(vals[3])
        
        self.show_home()

    def reset_home(self):
        self.origin_var.set("")
        self.dest_var.set("")
        self.dist_var.set("")
        if self.factors:
            self.ac_cb.current(0)
        self.rf_var.set(False)
        self.saf_var.set(0)
        self.saf_value_lbl.config(text="0%")
        
        for label in self.result_labels.values():
            label.config(text="—")
        
        self.suggestion_lbl.config(text="Enter flight details to see emissions and recommendations")

    def export_history(self, e=None):
        if not os.path.exists(HISTORY_CSV):
            show_modern_modal(self.root, "No History",
                            "No history file found to export.",
                            'info')
            return
        
        target = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            title="Export History"
        )
        
        if not target:
            return
        
        with open(HISTORY_CSV, 'r', encoding='utf-8') as src, \
             open(target, 'w', encoding='utf-8') as dst:
            dst.write(src.read())
        
        show_modern_modal(self.root, "Export Successful",
                        f"History exported to:\n{target}",
                        'success')

    def screenshot_window(self):
        self.root.update()
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after(200, lambda: self.root.attributes('-topmost', False))
        
        x = self.root.winfo_rootx()
        y = self.root.winfo_rooty()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        bbox = (x, y, x+w, y+h)
        
        try:
            img = ImageGrab.grab(bbox)
            os.makedirs("screenshots", exist_ok=True)
            name = f"screenshots/greenskies_{int(time.time())}.png"
            img.save(name)
            show_modern_modal(self.root, "Screenshot Saved",
                            f"Screenshot saved to:\n{name}",
                            'success')
        except Exception as e:
            show_modern_modal(self.root, "Screenshot Failed",
                            f"Could not save screenshot:\n{str(e)}",
                            'error')

# ---------- run ----------
def main():
    if not os.path.exists(EMISSION_CSV) or not os.path.exists(AIRPORTS_CSV):
        print(f"ERROR: Required CSV files missing!")
        print(f"Please ensure these files exist:")
        print(f"  - {EMISSION_CSV}")
        print(f"  - {AIRPORTS_CSV}")
        return
    
    root = tk.Tk()
    
    # Remove themed tk for better control
    root.configure(bg=COLORS['bg_primary'])
    
    app = GreenSkiesUltra(root)
    root.mainloop()

if __name__ == "__main__":
    main()
