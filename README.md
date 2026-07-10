# PDF-Sanitizer
Aplikasi batch untuk membersihkan PDF dari konstruksi berbahaya (`/URI`, JavaScript, OpenAction, Embedded Files) agar lolos validasi **JKN Drive BPJS**.

## Menjalankan sanitizer
Gunakan Python 3:

```bash
python sanitizer.py <input_dir> <output_dir>
```

Contoh:

```bash
python sanitizer.py ./pdf-masuk ./pdf-bersih
```

Semua file dengan ekstensi `.pdf` di `input_dir` akan diproses dan ditulis ulang ke `output_dir` dengan struktur folder yang sama.
