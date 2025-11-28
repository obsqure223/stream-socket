import flet as ft
from interface import TrisFletUI

def main(page: ft.Page):
    TrisFletUI(page)

if __name__ == "__main__":
    ft.app(target=main, assets_dir="assets")
