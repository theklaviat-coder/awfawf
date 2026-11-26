# -*- coding: utf-8 -*-
"""
Анализатор дискового пространства — проект «Пиксель и Код».
Автор: студент(ы) IT-команды. Стек: Python 3, Tkinter, matplotlib.

Возможности:
  1. Рекурсивное сканирование выбранной папки (с обработкой ошибок доступа).
  2. Топ-крупнейших файлов с сортировкой.
  3. Суммарный объём по расширениям (таблица).
  4. Столбчатая диаграмма по расширениям.
  5. Круговая диаграмма «крупные файлы vs остальное».
  6. Фильтр: показать только файлы крупнее заданного размера.
  7. Экспорт отчёта в CSV и сводки в TXT.
Запуск:  python disk_analyzer.py
"""

import os
import csv
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from collections import defaultdict

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_OK = True
except ImportError:
    MATPLOTLIB_OK = False


# ----------------------------- ЯДРО (без GUI) -----------------------------

def format_size(n: int) -> str:
    """Человекочитаемый размер: 1536 -> '1.5 КБ'."""
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if n < 1024 or unit == "ТБ":
            return f"{n:.1f} {unit}" if unit != "Б" else f"{int(n)} Б"
        n /= 1024


def scan_folder(path: str):
    """Рекурсивно обходит папку.
    Возвращает (файлы, по_расширениям, ошибки):
      файлы — [(полный_путь, размер_байт)],
      по_расширениям — {'.jpg': сумма_байт, ...},
      ошибки — [строки с описанием недоступных мест/файлов].
    """
    if not path or not os.path.isdir(path):
        raise ValueError(f"Путь не найден или это не папка: {path}")
    files, by_ext, errors = [], defaultdict(int), []

    def on_walk_error(e):
        errors.append(f"Нет доступа: {getattr(e, 'filename', e)}")

    for dirpath, _dirnames, filenames in os.walk(path, onerror=on_walk_error):
        for name in filenames:
            full = os.path.join(dirpath, name)
            try:
                size = os.path.getsize(full)
            except OSError as e:
                errors.append(str(e))
                continue
            ext = Path(name).suffix.lower() or "(без расширения)"
            files.append((full, size))
            by_ext[ext] += size
    return files, dict(by_ext), errors


def top_files(files, n=10):
    return sorted(files, key=lambda x: x[1], reverse=True)[:n]


def filter_by_size(files, min_bytes):
    return [(p, s) for p, s in files if s >= min_bytes]


def export_csv(files, path):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Путь", "Размер (байт)", "Размер (человекочитаемо)"])
        for p, s in files:
            w.writerow([p, s, format_size(s)])


def export_summary_txt(by_ext, files, path):
    total = sum(s for _, s in files)
    lines = [
        "ОТЧЁТ: анализ дискового пространства",
        f"Всего файлов: {len(files)}; общий объём: {format_size(total)}",
        "",
        "Объём по расширениям:",
    ]
    for ext, size in sorted(by_ext.items(), key=lambda x: -x[1]):
        share = size / total * 100 if total else 0
        lines.append(f"  {ext:<20} {format_size(size):>12} ({share:.1f}%)")
    lines += ["", "Топ-10 крупнейших файлов:"]
    for p, s in top_files(files, 10):
        lines.append(f"  {format_size(s):>12}  {p}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# -------------------------------- GUI -----------------------------------

class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Анализатор дискового пространства — «Пиксель и Код»")
        root.geometry("880x600")

        self.files = []      # [(путь, размер)]
        self.by_ext = {}     # {'.jpg': байт}
        self.errors = []

        self._build_ui()

    # --- построение интерфейса ---
    def _build_ui(self):
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="x")

        ttk.Label(top, text="Папка:").pack(side="left")
        self.path_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.path_var, width=60).pack(
            side="left", padx=6, fill="x", expand=True)
        ttk.Button(top, text="Обзор…", command=self.choose_folder).pack(side="left")
        ttk.Button(top, text="Сканировать", command=self.scan).pack(
            side="left", padx=6)

        # фильтр по минимальному размеру
        filt = ttk.Frame(self.root, padding=(8, 0))
        filt.pack(fill="x")
        ttk.Label(filt, text="Показывать файлы больше (КБ):").pack(side="left")
        self.min_kb = tk.StringVar(value="0")
        ttk.Spinbox(filt, from_=0, to=10**9, textvariable=self.min_kb,
                    width=10).pack(side="left", padx=6)
        ttk.Button(filt, text="Применить фильтр", command=self.apply_filter).pack(side="left")
        ttk.Button(filt, text="Сбросить", command=self.reset_filter).pack(side="left", padx=4)

        # кнопки диаграмм и экспорта
        acts = ttk.Frame(self.root, padding=8)
        acts.pack(fill="x")
        ttk.Button(acts, text="Диаграмма по расширениям",
                   command=self.show_bar).pack(side="left", padx=2)
        ttk.Button(acts, text="Круговая диаграмма",
                   command=self.show_pie).pack(side="left", padx=2)
        ttk.Button(acts, text="Экспорт CSV",
                   command=self.do_export_csv).pack(side="left", padx=2)
        ttk.Button(acts, text="Экспорт сводки TXT",
                   command=self.do_export_txt).pack(side="left", padx=2)

        # таблица
        columns = ("path", "size")
        self.tree = ttk.Treeview(self.root, columns=columns, show="headings")
        self.tree.heading("path", text="Файл")
        self.tree.heading("size", text="Размер")
        self.tree.column("path", width=640)
        self.tree.column("size", width=140, anchor="e")
        self.tree.pack(fill="both", expand=True, padx=8, pady=4)

        self.status = tk.StringVar(value="Выберите папку и нажмите «Сканировать».")
        ttk.Label(self.root, textvariable=self.status, padding=6,
                  relief="sunken", anchor="w").pack(fill="x", side="bottom")

    # --- действия ---
    def choose_folder(self):
        d = filedialog.askdirectory(title="Какую папку просканировать?")
        if d:
            self.path_var.set(d)

    def scan(self):
        path = self.path_var.get().strip()
        try:
            self.files, self.by_ext, self.errors = scan_folder(path)
        except ValueError as e:
            messagebox.showerror("Ошибка", str(e))
            return
        self.fill_tree(self.files)
        msg = f"Найдено файлов: {len(self.files)}. Общий объём: {format_size(sum(s for _, s in self.files))}."
        if self.errors:
            msg += f" Пропущено недоступных мест: {len(self.errors)}."
        self.status.set(msg)

    def fill_tree(self, rows):
        self.tree.delete(*self.tree.get_children())
        for p, s in sorted(rows, key=lambda x: -x[1]):
            self.tree.insert("", "end", values=(p, format_size(s)))

    def apply_filter(self):
        try:
            min_kb = int(self.min_kb.get())
        except ValueError:
            messagebox.showerror("Ошибка", "Введите целое число КБ, например 100.")
            return
        rows = filter_by_size(self.files, min_kb * 1024)
        self.fill_tree(rows)
        self.status.set(f"После фильтра показано файлов: {len(rows)} из {len(self.files)}.")

    def reset_filter(self):
        self.min_kb.set("0")
        self.fill_tree(self.files)
        self.status.set("Фильтр сброшен.")

    # --- диаграммы ---
    def show_bar(self):
        if not self._has_data():
            return
        items = sorted(self.by_ext.items(), key=lambda x: -x[1])[:10]
        labels = [e for e, _ in items]
        values = [s / (1024 * 1024) for _, s in items]  # МБ
        plt.figure(figsize=(9, 5))
        plt.bar(labels, values)
        plt.title("Объём по расширениям (МБ)")
        plt.ylabel("МБ")
        plt.tight_layout()
        plt.show()

    def show_pie(self):
        if not self._has_data():
            return
        top5 = sorted(self.by_ext.items(), key=lambda x: -x[1])[:5]
        rest = sum(s for _, s in self.by_ext.items()) - sum(s for _, s in top5)
        labels = [e for e, _ in top5] + (["остальное"] if rest > 0 else [])
        values = [s for _, s in top5] + ([rest] if rest > 0 else [])
        plt.figure(figsize=(6, 6))
        plt.pie(values, labels=labels, autopct="%1.1f%%")
        plt.title("Доли расширений в объёме")
        plt.show()

    # --- экспорт ---
    def do_export_csv(self):
        if not self._has_data():
            return
        p = filedialog.asksaveasfilename(defaultextension=".csv",
                                         filetypes=[("CSV", "*.csv")],
                                         initialfile="отчёт_файлы.csv")
        if not p:
            return
        try:
            export_csv(self.files, p)
            self.status.set(f"CSV сохранён: {p}")
        except OSError as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить файл:\n{e}")

    def do_export_txt(self):
        if not self._has_data():
            return
        p = filedialog.asksaveasfilename(defaultextension=".txt",
                                         filetypes=[("Текст", "*.txt")],
                                         initialfile="отчёт_сводка.txt")
        if not p:
            return
        try:
            export_summary_txt(self.by_ext, self.files, p)
            self.status.set(f"Сводка сохранена: {p}")
        except OSError as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить файл:\n{e}")

    def _has_data(self):
        if not self.files:
            messagebox.showinfo("Нет данных", "Сначала просканируйте папку.")
            return False
        return True


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("clam")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
