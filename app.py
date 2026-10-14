from __future__ import annotations

import math
import queue
import shutil
import tempfile
import threading
from pathlib import Path
from tkinter import Canvas, filedialog, messagebox
from uuid import uuid4

import customtkinter as ctk
from PIL import Image, ImageTk
from tkinterdnd2 import DND_FILES, TkinterDnD

from image_converter import convert_to_bmp


BACKGROUND = "#1C1C1C"
DROPZONE = "#202020"
TEXT = "#F2F2F2"
MUTED = "#A4A4A4"
PURPLE = "#8968F5"
PURPLE_HOVER = "#7654DF"
GREEN = "#07551F"
RED = "#9D211C"


class BmpicApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        TkinterDnD.require(self)

        ctk.set_appearance_mode("dark")
        self.title("Bmpic")
        self.iconbitmap(
            default=str(Path(__file__).resolve().parent / "assets" / "icon.ico")
        )
        self.geometry("340x350")
        self.resizable(False, False)
        self.configure(fg_color=BACKGROUND)

        self._state = "empty"
        self._source_path: Path | None = None
        self._preview_photo: ImageTk.PhotoImage | None = None
        self._empty_icon_photo: ImageTk.PhotoImage | None = None
        self._icons: dict[str, ctk.CTkImage] = {}
        self._temp_directory = tempfile.TemporaryDirectory(prefix="bmpic-")
        self._temp_bmp: Path | None = None
        self._worker_result: queue.Queue[tuple[bool, str]] = queue.Queue()
        self._preview_result: queue.Queue[
            tuple[bool, Path, Image.Image | None, str]
        ] = queue.Queue()
        self._state_before_loading = "empty"
        self._busy = False
        self._close_requested = False

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._render()
        self.update_idletasks()
        self._center_window()

    def _center_window(self) -> None:
        width = self.winfo_width()
        height = self.winfo_height()
        x = max(0, (self.winfo_screenwidth() - width) // 2)
        y = max(0, (self.winfo_screenheight() - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _build_ui(self) -> None:
        assets = Path(__file__).resolve().parent / "assets"
        for name, size in {
            "download": (18, 18),
            "trash": (18, 18),
        }.items():
            with Image.open(assets / f"{name}.png") as icon:
                image = icon.convert("RGBA")
                self._icons[name] = ctk.CTkImage(
                    light_image=image,
                    dark_image=image,
                    size=size,
                )
        with Image.open(assets / "image.png") as icon:
            empty_icon = icon.convert("RGBA")
            empty_icon.thumbnail((96, 96), Image.Resampling.LANCZOS)
            self._empty_icon_photo = ImageTk.PhotoImage(empty_icon)

        self.main = ctk.CTkFrame(self, fg_color="transparent")
        self.main.pack(fill="both", expand=True, padx=18, pady=16)

        self.dropzone = Canvas(
            self.main,
            width=384,
            height=190,
            background=DROPZONE,
            highlightthickness=0,
            cursor="hand2",
        )
        self.dropzone.pack(fill="x")
        self.dropzone.bind("<Button-1>", self._choose_image)
        self.dropzone.bind("<Configure>", lambda _event: self._draw_dropzone())
        self.dropzone.drop_target_register(DND_FILES)
        self.dropzone.dnd_bind("<<Drop>>", self._on_drop)

        self.status_frame = ctk.CTkFrame(
            self.main,
            height=34,
            corner_radius=9,
            fg_color="#292929",
        )
        self.status_frame.pack_propagate(False)

        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="Selecione uma imagem para converter",
            text_color=MUTED,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.status_label.pack(fill="both", expand=True, padx=10)

        self.progress = ctk.CTkProgressBar(
            self.main,
            height=4,
            mode="determinate",
            progress_color=PURPLE,
            fg_color="#303030",
        )

        self.actions = ctk.CTkFrame(self.main, fg_color="transparent")
        self.actions.pack(fill="x", pady=(14, 0))

        self.primary_button = ctk.CTkButton(
            self.actions,
            text="Converter",
            command=self._primary_action,
            height=40,
            corner_radius=9,
            fg_color=PURPLE,
            hover_color=PURPLE_HOVER,
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.primary_button.pack(side="left", fill="x", expand=True)

        self.clear_button = ctk.CTkButton(
            self.actions,
            text="",
            image=self._icons["trash"],
            command=self._reset,
            width=48,
            height=40,
            corner_radius=9,
            fg_color=RED,
            hover_color="#7D1814",
            text_color="#FFFFFF",
        )

        self.progress.pack(fill="x", pady=(12, 0))
        self.status_frame.pack(fill="x", pady=(9, 0))

    def _draw_dropzone(self) -> None:
        if not hasattr(self, "dropzone"):
            return

        self.dropzone.delete("all")
        width = max(self.dropzone.winfo_width(), 300)
        height = max(self.dropzone.winfo_height(), 150)
        left, top, right, bottom = 8, 8, width - 8, height - 8
        radius = 18
        points = [(left + radius, top), (right - radius, top)]
        corners = (
            (right - radius, top + radius, -90),
            (right - radius, bottom - radius, 0),
            (left + radius, bottom - radius, 90),
            (left + radius, top + radius, 180),
        )
        for index, (center_x, center_y, start_angle) in enumerate(corners):
            for step in range(1, 7):
                angle = math.radians(start_angle + step * 15)
                points.append(
                    (
                        center_x + radius * math.cos(angle),
                        center_y + radius * math.sin(angle),
                    )
                )
            if index == 0:
                points.append((right, bottom - radius))
            elif index == 1:
                points.append((left + radius, bottom))
            elif index == 2:
                points.append((left, top + radius))
        points.append(points[0])
        self.dropzone.create_line(
            *(coordinate for point in points for coordinate in point),
            fill="#777777",
            width=2,
            dash=(12, 9),
            capstyle="round",
            joinstyle="round",
        )

        if self._source_path is None:
            if self._empty_icon_photo is not None:
                self.dropzone.create_image(
                    width / 2,
                    height / 2 - 18,
                    image=self._empty_icon_photo,
                    anchor="center",
                )
            self.dropzone.create_text(
                width / 2,
                height / 2 + 35,
                text="Clique ou arraste uma\nimagem PNG ou JPG",
                fill="#C4C4C4",
                font=("Segoe UI", 11),
                width=width - 34,
                justify="center",
            )
            return

        if self._preview_photo is not None:
            self.dropzone.create_image(
                width / 2,
                height / 2 - 12,
                image=self._preview_photo,
                anchor="center",
            )
        self.dropzone.create_text(
            width / 2,
            height - 25,
            text=self._source_path.name,
            fill="#C4C4C4",
            font=("Segoe UI", 11),
            width=width - 34,
            justify="center",
        )

    def _render(self) -> None:
        self._draw_dropzone()
        self.progress.stop()
        self.clear_button.pack_forget()
        self.status_frame.configure(fg_color="transparent")

        if self._state == "empty":
            self.progress.configure(mode="determinate", progress_color=PURPLE)
            self.progress.set(0)
            self.status_label.configure(
                text="Selecione uma imagem para converter", text_color=MUTED
            )
            self.primary_button.configure(
                text="Converter",
                state="disabled",
                fg_color="#555555",
                hover_color="#555555",
                text_color="#BDBDBD",
            )
        elif self._state == "loaded":
            self.progress.configure(mode="determinate", progress_color=PURPLE)
            self.progress.set(0)
            self.status_label.configure(
                text="Imagem pronta para converter", text_color=MUTED
            )
            self.primary_button.configure(
                text="Converter",
                state="normal",
                fg_color=PURPLE,
                hover_color=PURPLE_HOVER,
                text_color="#FFFFFF",
            )
        elif self._state in {"loading", "converting"}:
            self.progress.configure(mode="indeterminate", progress_color=PURPLE)
            self.progress.set(0)
            status = "Abrindo imagem…" if self._state == "loading" else "Convertendo imagem"
            button_text = "Carregando" if self._state == "loading" else "Convertendo"
            self.status_label.configure(text=status, text_color=MUTED)
            self.primary_button.configure(
                text=button_text,
                state="disabled",
                fg_color="#493A84",
                hover_color="#493A84",
                text_color="#E4DFFF",
            )
            self.progress.start()
        elif self._state == "completed":
            self.progress.configure(mode="determinate", progress_color="#32951F")
            self.progress.set(1)
            self.status_label.configure(text="Concluído", text_color="#32951F")
            self.primary_button.configure(
                text="Salvar",
                image=self._icons["download"],
                compound="left",
                state="normal",
                fg_color=PURPLE,
                hover_color=PURPLE_HOVER,
                text_color="#FFFFFF",
            )
            self.clear_button.pack(side="left", padx=(8, 0))
        if self._state != "completed":
            self.primary_button.configure(image=None, compound="left")

    def _choose_image(self, _event=None) -> None:
        if self._busy:
            return
        selected = filedialog.askopenfilename(
            parent=self,
            title="Escolher imagem",
            filetypes=[("Imagens", "*.jpg *.jpeg *.png"), ("Todos os arquivos", "*.*")],
        )
        if selected:
            self._select_image(Path(selected))

    def _on_drop(self, event) -> str:
        if self._busy:
            return "break"
        paths = self.tk.splitlist(event.data)
        if paths:
            self._select_image(Path(paths[0]))
        return "break"

    def _select_image(self, path: Path) -> None:
        if self._busy:
            return
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            messagebox.showerror(
                "Formato não suportado",
                "Escolha uma imagem JPG ou PNG.",
                parent=self,
            )
            return

        self._state_before_loading = self._state
        self._busy = True
        self._state = "loading"
        self._render()
        worker = threading.Thread(
            target=self._preview_worker,
            args=(path,),
            daemon=True,
        )
        worker.start()
        self.after(100, self._poll_preview_worker)

    def _preview_worker(self, path: Path) -> None:
        try:
            with Image.open(path) as source:
                source.load()
                source.thumbnail((260, 126), Image.Resampling.LANCZOS)
                preview = source.copy()
                if "A" in preview.getbands() or "transparency" in preview.info:
                    preview = preview.convert("RGBA")
                else:
                    preview = preview.convert("RGB")
            self._preview_result.put((True, path, preview, ""))
        except (OSError, ValueError, Image.DecompressionBombError) as error:
            self._preview_result.put((False, path, None, str(error)))

    def _poll_preview_worker(self) -> None:
        try:
            succeeded, path, preview, error = self._preview_result.get_nowait()
        except queue.Empty:
            self.after(100, self._poll_preview_worker)
            return

        self._busy = False
        if self._close_requested:
            self._finish_close()
            return

        if not succeeded or preview is None:
            self._state = self._state_before_loading
            self._render()
            messagebox.showerror(
                "Imagem inválida",
                f"Não foi possível abrir essa imagem.\n\n{error}",
                parent=self,
            )
            return

        self._discard_temporary_result()
        self._source_path = path
        self._preview_photo = ImageTk.PhotoImage(preview)
        self._state = "loaded"
        self._render()

    def _primary_action(self) -> None:
        if self._state == "loaded":
            self._start_conversion()
        elif self._state == "completed":
            self._save_result()

    def _start_conversion(self) -> None:
        if self._source_path is None or self._busy:
            return

        self._discard_temporary_result()
        self._temp_bmp = Path(self._temp_directory.name) / f"{uuid4().hex}.bmp"
        input_path = self._source_path
        output_path = self._temp_bmp
        self._busy = True
        self._state = "converting"
        self._render()

        worker = threading.Thread(
            target=self._convert_worker,
            args=(input_path, output_path),
            daemon=True,
        )
        worker.start()
        self.after(100, self._poll_worker)

    def _convert_worker(self, input_path: Path, output_path: Path) -> None:
        try:
            convert_to_bmp(input_path, output_path)
            self._worker_result.put((True, ""))
        except Exception as error:
            self._worker_result.put((False, str(error)))

    def _poll_worker(self) -> None:
        try:
            succeeded, error = self._worker_result.get_nowait()
        except queue.Empty:
            self.after(100, self._poll_worker)
            return

        self._busy = False
        if self._close_requested:
            self._finish_close()
            return

        self.progress.stop()
        if succeeded:
            self._state = "completed"
            self._render()
        else:
            self._discard_temporary_result()
            self._state = "loaded"
            self._render()
            messagebox.showerror(
                "Falha na conversão",
                f"Não foi possível converter a imagem.\n\n{error}",
                parent=self,
            )

    def _save_result(self) -> None:
        if self._temp_bmp is None or not self._temp_bmp.exists() or self._source_path is None:
            return

        selected = filedialog.asksaveasfilename(
            parent=self,
            title="Salvar BMP",
            initialdir=Path.home(),
            initialfile=f"{self._source_path.stem}.bmp",
            defaultextension=".bmp",
            filetypes=[("Imagem BMP", "*.bmp")],
            confirmoverwrite=True,
        )
        if not selected:
            self._discard_temporary_result()
            self._state = "loaded"
            self._render()
            return

        destination = Path(selected)
        if destination.suffix.lower() != ".bmp":
            messagebox.showerror(
                "Formato inválido",
                "Escolha um nome de arquivo com a extensão .bmp.",
                parent=self,
            )
            return

        try:
            shutil.copyfile(self._temp_bmp, destination)
        except OSError as error:
            messagebox.showerror(
                "Falha ao salvar",
                f"Não foi possível salvar o BMP nesse local.\n\n{error}",
                parent=self,
            )
            return

        self.status_label.configure(text=f"Salvo: {destination.name}", text_color="#FFFFFF")
        messagebox.showinfo(
            "BMP salvo",
            f"Imagem salva com sucesso em:\n{destination}",
            parent=self,
        )

    def _discard_temporary_result(self) -> None:
        if self._temp_bmp is not None:
            try:
                self._temp_bmp.unlink(missing_ok=True)
            except OSError:
                pass
            self._temp_bmp = None

    def _reset(self) -> None:
        if self._busy:
            return
        self._discard_temporary_result()
        self._source_path = None
        self._preview_photo = None
        self._state = "empty"
        self._render()

    def _on_close(self) -> None:
        if self._busy:
            self._close_requested = True
            self.status_label.configure(text="Finalizando conversão antes de fechar…")
            return
        self._finish_close()

    def _finish_close(self) -> None:
        self._discard_temporary_result()
        self._temp_directory.cleanup()
        self.destroy()


def main() -> None:
    app = BmpicApp()
    app.mainloop()


if __name__ == "__main__":
    main()
