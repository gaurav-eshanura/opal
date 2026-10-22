# Opal - Every-Feature Verification Report

- Generated: 2026-10-22 08:41:30
- Suite: `tests/test_every_feature.py`
- Result: **166 passed, 0 failed** (166 checks in total)

The suite runs every action in `OpalEngine.get_catalog()` against real sample files, opens every dialog and modal surface headless, exercises every public function in `opal_studio/platform_compat.py` and drives the CLI. Output files are re-opened with the matching reader (PIL / PyMuPDF / zipfile) so a "successful" conversion that produced a broken file counts as a failure.

### Areas covered

| Area | Checks |
|------|--------|
| CATALOG - every action run for real | 58 (58 passed, 0 failed) |
| MODULES - every opal_studio module imports cleanly | 33 (33 passed, 0 failed) |
| DIALOGS - every modal surface opens | 49 (49 passed, 0 failed) |
| CROSS-PLATFORM LAYER | 15 (15 passed, 0 failed) |
| COMMAND LINE | 11 (11 passed, 0 failed) |

### Engines available on this machine

| Engine | State |
|--------|-------|
| FFmpeg | C:\Users\shiva\antigravity\quirky-euclid\ffmpeg_backup\ffmpeg.exe |
| onnxruntime | 1.27.0 |
| AI cut-out model (u2netp) | cached at C:\Users\shiva\AppData\Roaming\Opal\models\u2netp.onnx |
| AI upscale model (realesrgan-x4plus) | cached at C:\Users\shiva\AppData\Roaming\Opal\models\realesrgan-x4plus.onnx |
| PDF signing (pyHanko) | installed |
| OCR (RapidOCR) | available |
| Network | reachable |
| Free RAM during the run | 3.3 GB free of 16.9 GB |

## Notes

- The suite touches the real desktop on purpose: `reveal_in_file_manager()`, `open_with_default()` and `open_terminal()` really open Explorer, the default app and a PowerShell window, and `send_to_trash()` really uses the Recycle Bin.
- The user's own `config.json` and the `HKCU\...\Run` startup entry are snapshotted before the run and written back afterwards, and the outputs are forced next to the sample files so the run never depends on a saved preference.
- Every AI action runs the real model. `u2netp.onnx` is cached locally and the cut-out is proven by the transparency of the produced PNG; the Real-ESRGAN model is downloaded on first use and verified by the product's own checksum check.
- The memory numbers in the table matter: the Real-ESRGAN model needs a large contiguous allocation, so on a busy machine its failures are allocator errors, not logic errors. Those checks are reported as environment problems, with the free RAM at the time of the run.

## Full results

| # | Area | Feature | Result | Detail |
|---|------|---------|--------|--------|
| 1 | CATALOG - every action run for real | catalog is not empty | PASS |  |
| 2 | CATALOG - every action run for real | every catalog id has a test fixture | PASS |  |
| 3 | CATALOG - every action run for real | no test runs an action the catalog does not advertise | PASS |  |
| 4 | CATALOG - every action run for real | catalog action 'remove_bg' | PASS |  |
| 5 | CATALOG - every action run for real | catalog action 'aadhaar_photo' | PASS |  |
| 6 | CATALOG - every action run for real | catalog action 'print_4x6' | PASS |  |
| 7 | CATALOG - every action run for real | catalog action 'photo_whatsapp' | PASS |  |
| 8 | CATALOG - every action run for real | catalog action 'pdf_whatsapp' | PASS |  |
| 9 | CATALOG - every action run for real | catalog action 'pdf_a4' | PASS |  |
| 10 | CATALOG - every action run for real | catalog action 'add_border' | PASS |  |
| 11 | CATALOG - every action run for real | catalog action 'bg_cutout_blur' | PASS |  |
| 12 | CATALOG - every action run for real | catalog action 'upscale_2x' | PASS |  |
| 13 | CATALOG - every action run for real | catalog action 'enhance_auto' | PASS |  |
| 14 | CATALOG - every action run for real | catalog action 'compress_image' | PASS |  |
| 15 | CATALOG - every action run for real | catalog action 'social_portrait' | PASS |  |
| 16 | CATALOG - every action run for real | catalog action 'color_palette' | PASS |  |
| 17 | CATALOG - every action run for real | catalog action 'exif_report' | PASS |  |
| 18 | CATALOG - every action run for real | catalog action 'watermark_image' | PASS |  |
| 19 | CATALOG - every action run for real | catalog action 'qr_code' | PASS |  |
| 20 | CATALOG - every action run for real | catalog action 'pdf' | PASS |  |
| 21 | CATALOG - every action run for real | catalog action 'pptx' | PASS |  |
| 22 | CATALOG - every action run for real | catalog action 'docx' | PASS |  |
| 23 | CATALOG - every action run for real | catalog action 'epub' | PASS |  |
| 24 | CATALOG - every action run for real | catalog action 'pdf_dsc_sign' | PASS |  |
| 25 | CATALOG - every action run for real | catalog action 'pdf_pagenum' | PASS |  |
| 26 | CATALOG - every action run for real | catalog action 'pdf_watermark' | PASS |  |
| 27 | CATALOG - every action run for real | catalog action 'pdf_ocr' | PASS |  |
| 28 | CATALOG - every action run for real | catalog action 'split_pdf' | PASS |  |
| 29 | CATALOG - every action run for real | catalog action 'epub_txt' | PASS |  |
| 30 | CATALOG - every action run for real | catalog action 'md_html' | PASS |  |
| 31 | CATALOG - every action run for real | catalog action 'srt_vtt' | PASS |  |
| 32 | CATALOG - every action run for real | catalog action 'csv_xlsx' | PASS |  |
| 33 | CATALOG - every action run for real | catalog action 'font_report' | PASS |  |
| 34 | CATALOG - every action run for real | catalog action 'video_thumbnails' | PASS |  |
| 35 | CATALOG - every action run for real | catalog action 'video_frames' | PASS |  |
| 36 | CATALOG - every action run for real | catalog action 'burn_subtitles' | PASS |  |
| 37 | CATALOG - every action run for real | catalog action 'hash_file' | PASS |  |
| 38 | CATALOG - every action run for real | catalog action 'quick_zip' | PASS |  |
| 39 | CATALOG - every action run for real | catalog action 'merge_pdf' | PASS |  |
| 40 | CATALOG - every action run for real | extra action 'join_photos' | PASS |  |
| 41 | CATALOG - every action run for real | extra action 'compress_media' | PASS |  |
| 42 | CATALOG - every action run for real | extra action 'video_720p' | PASS |  |
| 43 | CATALOG - every action run for real | extra action 'mute_video' | PASS |  |
| 44 | CATALOG - every action run for real | extra action 'trim_30s' | PASS |  |
| 45 | CATALOG - every action run for real | extra action 'video_speed' | PASS |  |
| 46 | CATALOG - every action run for real | extra action 'audio_normalize' | PASS |  |
| 47 | CATALOG - every action run for real | extra action 'audio_speed' | PASS |  |
| 48 | CATALOG - every action run for real | extra action 'video_rotate' | PASS |  |
| 49 | CATALOG - every action run for real | AI cut-out model resolves to the cached u2netp.onnx | PASS |  |
| 50 | CATALOG - every action run for real | remove_bg produced real transparency (AI matting ran) | PASS |  |
| 51 | CATALOG - every action run for real | AI Upscale cache holds a real ONNX model, not an HTML error page | PASS |  |
| 52 | CATALOG - every action run for real | AI Upscale handles a full-size (640x480) photo | PASS |  |
| 53 | CATALOG - every action run for real | the AI cut-out model is still on disk after the run | PASS |  |
| 54 | CATALOG - every action run for real | the cached AI cut-out model loads in ONNX Runtime | PASS |  |
| 55 | CATALOG - every action run for real | AI Upscale model URL for 'realesrgan-x4plus' is reachable | PASS |  |
| 56 | CATALOG - every action run for real | AI Upscale model URL for 'realesrgan-x2plus' is reachable | PASS |  |
| 57 | CATALOG - every action run for real | pdf_dsc_sign embedded a real cryptographic signature | PASS |  |
| 58 | CATALOG - every action run for real | pdf_ocr left a searchable text layer on the scan | PASS |  |
| 59 | MODULES - every opal_studio module imports cleanly | module opal_studio.brand imports | PASS |  |
| 60 | MODULES - every opal_studio module imports cleanly | module opal_studio.cli imports | PASS |  |
| 61 | MODULES - every opal_studio module imports cleanly | module opal_studio.config imports | PASS |  |
| 62 | MODULES - every opal_studio module imports cleanly | module opal_studio.context_menu imports | PASS |  |
| 63 | MODULES - every opal_studio module imports cleanly | module opal_studio.dashboard imports | PASS |  |
| 64 | MODULES - every opal_studio module imports cleanly | module opal_studio.drag_detector imports | PASS |  |
| 65 | MODULES - every opal_studio module imports cleanly | module opal_studio.drop_orb imports | PASS |  |
| 66 | MODULES - every opal_studio module imports cleanly | module opal_studio.dsc_sign imports | PASS |  |
| 67 | MODULES - every opal_studio module imports cleanly | module opal_studio.engine imports | PASS |  |
| 68 | MODULES - every opal_studio module imports cleanly | module opal_studio.engine_packs imports | PASS |  |
| 69 | MODULES - every opal_studio module imports cleanly | module opal_studio.engines imports | PASS |  |
| 70 | MODULES - every opal_studio module imports cleanly | module opal_studio.float_viewer imports | PASS |  |
| 71 | MODULES - every opal_studio module imports cleanly | module opal_studio.glass imports | PASS |  |
| 72 | MODULES - every opal_studio module imports cleanly | module opal_studio.history_dialog imports | PASS |  |
| 73 | MODULES - every opal_studio module imports cleanly | module opal_studio.hotkey imports | PASS |  |
| 74 | MODULES - every opal_studio module imports cleanly | module opal_studio.icons imports | PASS |  |
| 75 | MODULES - every opal_studio module imports cleanly | module opal_studio.input_watch imports | PASS |  |
| 76 | MODULES - every opal_studio module imports cleanly | module opal_studio.main imports | PASS |  |
| 77 | MODULES - every opal_studio module imports cleanly | module opal_studio.pdf_tools imports | PASS |  |
| 78 | MODULES - every opal_studio module imports cleanly | module opal_studio.platform_compat imports | PASS |  |
| 79 | MODULES - every opal_studio module imports cleanly | module opal_studio.radial_widget imports | PASS |  |
| 80 | MODULES - every opal_studio module imports cleanly | module opal_studio.safepath imports | PASS |  |
| 81 | MODULES - every opal_studio module imports cleanly | module opal_studio.settings_dialog imports | PASS |  |
| 82 | MODULES - every opal_studio module imports cleanly | module opal_studio.theme imports | PASS |  |
| 83 | MODULES - every opal_studio module imports cleanly | module opal_studio.toast imports | PASS |  |
| 84 | MODULES - every opal_studio module imports cleanly | module opal_studio.tray imports | PASS |  |
| 85 | MODULES - every opal_studio module imports cleanly | module opal_studio.viewer_doc imports | PASS |  |
| 86 | MODULES - every opal_studio module imports cleanly | module opal_studio.viewer_image imports | PASS |  |
| 87 | MODULES - every opal_studio module imports cleanly | module opal_studio.viewer_media imports | PASS |  |
| 88 | MODULES - every opal_studio module imports cleanly | module opal_studio.viewer_pdf imports | PASS |  |
| 89 | MODULES - every opal_studio module imports cleanly | module opal_studio.watch_folder imports | PASS |  |
| 90 | MODULES - every opal_studio module imports cleanly | module opal_studio.worker imports | PASS |  |
| 91 | MODULES - every opal_studio module imports cleanly | every opal_studio module imports without error | PASS |  |
| 92 | DIALOGS - every modal surface opens | SettingsDialog opens without crashing | PASS |  |
| 93 | DIALOGS - every modal surface opens | SettingsDialog is visible | PASS |  |
| 94 | DIALOGS - every modal surface opens | SettingsDialog shows the AI model pickers | PASS |  |
| 95 | DIALOGS - every modal surface opens | SettingsDialog buttons are wired | PASS |  |
| 96 | DIALOGS - every modal surface opens | SettingsDialog 'Save Preferences' button works | PASS |  |
| 97 | DIALOGS - every modal surface opens | SettingsDialog save persisted the preferences | PASS |  |
| 98 | DIALOGS - every modal surface opens | HistoryDialog opens without crashing | PASS |  |
| 99 | DIALOGS - every modal surface opens | HistoryDialog is visible | PASS |  |
| 100 | DIALOGS - every modal surface opens | HistoryDialog lists recorded runs | PASS |  |
| 101 | DIALOGS - every modal surface opens | SignatureDialog opens without crashing | PASS |  |
| 102 | DIALOGS - every modal surface opens | SignatureDialog is visible | PASS |  |
| 103 | DIALOGS - every modal surface opens | SignatureDialog has draw / type / image tabs | PASS |  |
| 104 | DIALOGS - every modal surface opens | SignatureDialog type tab renders a signature | PASS |  |
| 105 | DIALOGS - every modal surface opens | SignatureDialog draw tab captures strokes | PASS |  |
| 106 | DIALOGS - every modal surface opens | SignatureDialog image tab produces a signature PNG | PASS |  |
| 107 | DIALOGS - every modal surface opens | PdfStudio opens without crashing | PASS |  |
| 108 | DIALOGS - every modal surface opens | PdfStudio is visible | PASS |  |
| 109 | DIALOGS - every modal surface opens | PdfStudio loaded the document | PASS |  |
| 110 | DIALOGS - every modal surface opens | PdfStudio built a page view per page | PASS |  |
| 111 | DIALOGS - every modal surface opens | PdfStudio built page thumbnails | PASS |  |
| 112 | DIALOGS - every modal surface opens | _range_dialog opens and returns the typed range | PASS |  |
| 113 | DIALOGS - every modal surface opens | ImageLab opens without crashing | PASS |  |
| 114 | DIALOGS - every modal surface opens | ImageLab is visible | PASS |  |
| 115 | DIALOGS - every modal surface opens | ImageLab loaded the picture | PASS |  |
| 116 | DIALOGS - every modal surface opens | ImageLab palette tool produces swatches | PASS |  |
| 117 | DIALOGS - every modal surface opens | DocStudio opens without crashing | PASS |  |
| 118 | DIALOGS - every modal surface opens | DocStudio is visible | PASS |  |
| 119 | DIALOGS - every modal surface opens | DocStudio rendered the text | PASS |  |
| 120 | DIALOGS - every modal surface opens | MediaStudio opens without crashing | PASS |  |
| 121 | DIALOGS - every modal surface opens | MediaStudio is visible | PASS |  |
| 122 | DIALOGS - every modal surface opens | MediaStudio read the media duration | PASS |  |
| 123 | DIALOGS - every modal surface opens | OpalDashboard opens without crashing | PASS |  |
| 124 | DIALOGS - every modal surface opens | OpalDashboard is visible | PASS |  |
| 125 | DIALOGS - every modal surface opens | FloatStudio opens without crashing | PASS |  |
| 126 | DIALOGS - every modal surface opens | FloatStudio is visible | PASS |  |
| 127 | DIALOGS - every modal surface opens | FloatStudio starts on the Home tab | PASS |  |
| 128 | DIALOGS - every modal surface opens | FloatStudio opens a file in a new tab | PASS |  |
| 129 | DIALOGS - every modal surface opens | FloatStudio HomeTab opens without crashing | PASS |  |
| 130 | DIALOGS - every modal surface opens | FloatStudio HomeTab is visible | PASS |  |
| 131 | DIALOGS - every modal surface opens | RadialMenuWidget opens without crashing | PASS |  |
| 132 | DIALOGS - every modal surface opens | RadialMenuWidget is visible | PASS |  |
| 133 | DIALOGS - every modal surface opens | RadialMenuWidget 'convert' mode lists conversions | PASS |  |
| 134 | DIALOGS - every modal surface opens | RadialMenuWidget 'tools' mode lists tools | PASS |  |
| 135 | DIALOGS - every modal surface opens | RadialMenuWidget 'actions' mode lists actions | PASS |  |
| 136 | DIALOGS - every modal surface opens | OpalToast opens without crashing | PASS |  |
| 137 | DIALOGS - every modal surface opens | OpalToast is visible | PASS |  |
| 138 | DIALOGS - every modal surface opens | OpalToast shows the action buttons | PASS |  |
| 139 | DIALOGS - every modal surface opens | OpalTray opens without crashing | PASS |  |
| 140 | DIALOGS - every modal surface opens | OpalTray has a context menu | PASS |  |
| 141 | CROSS-PLATFORM LAYER | platform_name() returns the OS name | PASS |  |
| 142 | CROSS-PLATFORM LAYER | startup_supported() returns a bool | PASS |  |
| 143 | CROSS-PLATFORM LAYER | context_menu_supported() returns a bool | PASS |  |
| 144 | CROSS-PLATFORM LAYER | portable_root() returns a path or None | PASS |  |
| 145 | CROSS-PLATFORM LAYER | user_data_dir() returns an existing folder | PASS |  |
| 146 | CROSS-PLATFORM LAYER | is_portable() agrees with portable_root() | PASS |  |
| 147 | CROSS-PLATFORM LAYER | copy_text_to_clipboard() works | PASS |  |
| 148 | CROSS-PLATFORM LAYER | send_to_trash() removes the file | PASS |  |
| 149 | CROSS-PLATFORM LAYER | set_startup_entry(True) registers the app | PASS |  |
| 150 | CROSS-PLATFORM LAYER | set_startup_entry(False) removes the app | PASS |  |
| 151 | CROSS-PLATFORM LAYER | install_context_menu() registers the entry | PASS |  |
| 152 | CROSS-PLATFORM LAYER | uninstall_context_menu() removes the entry | PASS |  |
| 153 | CROSS-PLATFORM LAYER | reveal_in_file_manager() opens Explorer on the file | PASS |  |
| 154 | CROSS-PLATFORM LAYER | open_with_default() opens the file with its default app | PASS |  |
| 155 | CROSS-PLATFORM LAYER | open_terminal() opens a terminal in the folder | PASS |  |
| 156 | COMMAND LINE | CLI --catalog exits 0 | PASS |  |
| 157 | COMMAND LINE | CLI --catalog prints the whole catalog | PASS |  |
| 158 | COMMAND LINE | CLI --list-formats exits 0 | PASS |  |
| 159 | COMMAND LINE | CLI --list-formats prints every format group | PASS |  |
| 160 | COMMAND LINE | CLI --info exits 0 | PASS |  |
| 161 | COMMAND LINE | CLI --info prints machine-readable JSON about the file | PASS |  |
| 162 | COMMAND LINE | CLI --convert exits 0 | PASS |  |
| 163 | COMMAND LINE | CLI --convert really produced a file | PASS |  |
| 164 | COMMAND LINE | CLI --convert output is a valid WebP | PASS |  |
| 165 | COMMAND LINE | CLI --tool exits 0 | PASS |  |
| 166 | COMMAND LINE | CLI --tool really ran the AI cut-out | PASS |  |

## Failures

No failures: every feature checked works end to end.
