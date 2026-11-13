from gui import InvoiceGeneratorApp
from invoice import InvoiceBackend


def main():
    backend = InvoiceBackend()
    app = InvoiceGeneratorApp(backend=backend)
    app.mainloop()


if __name__ == "__main__":
    main()
