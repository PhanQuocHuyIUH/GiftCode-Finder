# 🎁 GiftCode Finder

Tự động lấy giftcode game từ các trang web, cập nhật mỗi giờ bằng GitHub Actions.
Mở link là có code, bấm vào code là sao chép.

**👉 Xem code: https://phanquochuyiuh.github.io/GiftCode-Finder/**

(Bảng bên dưới cũng tự cập nhật, dùng được ngay cả khi chưa bật trang web.)

## Code hiện có

<!-- GIFTCODES:START -->
### Strinova — 0 code

_Chưa có code nào đang hoạt động._

Nguồn: [Gzone (zoneplay.vn)](https://zoneplay.vn/care/game/367)

_Code thay đổi lần cuối: 23/10/2026 18:57 (giờ Việt Nam)._
<!-- GIFTCODES:END -->

## Cách hoạt động

1. Workflow [`Lấy giftcode`](.github/workflows/scrape.yml) chạy mỗi giờ (và mỗi khi sửa cấu hình).
2. Nó đọc [`config/sources.yaml`](config/sources.yaml), tải từng trang nguồn và lấy code ra.
   Một game có thể có nhiều nguồn, code trùng giữa các nguồn được gộp lại.
3. Kết quả gộp với lịch sử trong [`data/codes.json`](data/codes.json): code mới được ghi ngày
   phát hiện (hiện nhãn **MỚI** trong 3 ngày), code bị gỡ khỏi trang nguồn chuyển sang mục "code cũ".
4. Trang web được dựng lại và đăng lên GitHub Pages; bảng code ở README này cũng được cập nhật
   (chỉ commit khi danh sách code thay đổi).

Nếu một trang nguồn bị lỗi (sập, đổi giao diện), code cũ của nguồn đó vẫn được giữ và trang web
hiện cảnh báo, chứ không xoá sạch danh sách.

### Strinova lấy code từ đâu?

| Nguồn | Lấy được gì |
|---|---|
| [Bài *Hướng dẫn nhập giftcode Strinova VN*](https://strinova.zoneplay.vn/huong-dan/huong-dan-nhap-giftcode-strinova-vn) | Danh sách code công khai do Gzone đăng |
| [Gzone Care](https://zoneplay.vn/care/game/367) | Danh sách sự kiện giftcode. Gzone **chỉ hiện mã khi đã đăng nhập**, nên không có token thì trang web liệt kê sự kiện kèm link *Nhận code*; có token thì tự lấy mã |

## Cài đặt một lần

1. **Bật trang web:** vào **Settings → Pages**, mục *Build and deployment → Source* chọn
   **GitHub Actions**.
2. Vào tab **Actions → Lấy giftcode → Run workflow** để chạy lần đầu (sau đó nó tự chạy mỗi giờ).
3. Mở https://phanquochuyiuh.github.io/GiftCode-Finder/ — nên lưu link này ra màn hình chính
   điện thoại.

Muốn lấy code ngay không chờ lịch: bấm **Quét lại ngay** trên trang web (mở trang Actions),
rồi **Run workflow**.

> GitHub tự tạm dừng lịch chạy của repo public nếu repo không có hoạt động nào trong 60 ngày.
> Khi đó vào **Actions → Lấy giftcode → Enable workflow** để bật lại.

### (Tuỳ chọn) Cho phép tự lấy mã trên Gzone Care

Trang Gzone Care chỉ trả mã cho tài khoản đã đăng nhập. Nếu muốn hệ thống tự lấy mã của các sự
kiện mới (kể cả trước khi Gzone đăng bài hướng dẫn):

1. Đăng nhập https://zoneplay.vn trên máy tính, nhấn **F12 → Console**, gõ
   `localStorage.access_token` rồi Enter, sao chép chuỗi hiện ra (bỏ dấu nháy).
2. Vào **Settings → Secrets and variables → Actions → New repository secret**, đặt tên
   `ZONEPLAY_ACCESS_TOKEN`, dán chuỗi vừa chép.
3. Chạy lại workflow.

Lưu ý:

- Token là phiên đăng nhập tài khoản Gzone của bạn. Secret của GitHub được mã hoá và bị che
  trong log, nhưng chỉ nên dùng nếu bạn chấp nhận điều đó.
- Hệ thống chỉ lấy và đăng công khai **giftcode chung** (mọi người dùng chung một mã). Giftcode
  riêng/voucher gắn với tài khoản chỉ được liệt kê kèm link, không bao giờ bị lấy hay đăng lên web.
- Khi token hết hạn, trang web hiện cảnh báo của nguồn Gzone Care; code đã lấy trước đó vẫn được
  giữ. Lặp lại bước 1–2 để cập nhật token.

## Thêm game hoặc trang nguồn

Mọi thứ nằm trong [`config/sources.yaml`](config/sources.yaml).

**Game khác trên Gzone** — đổi số id trong link Care:

```yaml
  - id: ten-game
    name: Tên Game
    sources:
      - id: gzone
        name: Gzone Care (zoneplay.vn)
        type: zoneplay
        url: https://zoneplay.vn/care/game/<id>
```

**Trang bất kỳ, lấy bằng CSS selector** (ví dụ bài hướng dẫn giftcode của game):

```yaml
      - id: huong-dan
        name: Bài hướng dẫn giftcode
        type: html
        url: https://example.com/giftcode
        code: "#article li"         # phần tử chứa code
        # item: ".giftcode-item"    # hoặc: khối chứa một code, rồi code/reward/expires bên trong
        # reward: ".reward"         # phần thưởng (tuỳ chọn)
        # expires: ".expired"       # hạn dùng (tuỳ chọn)
        # attr: data-clipboard-text # lấy code từ thuộc tính thay vì chữ
        # render: true              # trang dựng bằng JavaScript -> dùng trình duyệt headless
```

**Trang bài viết, lấy bằng regex:**

```yaml
      - id: blog
        type: regex
        url: https://example.com/bai-viet-giftcode
        pattern: 'Code:\s*(?P<code>[A-Z0-9]+)\s*-\s*(?P<reward>[^\n]+)'
```

**API JSON:**

```yaml
      - id: api
        type: json
        url: https://api.example.com/giftcodes?game=1
        items: data.list            # đường dẫn tới mảng code (bỏ trống = tự tìm)
        code: code                  # tên trường chứa code
        reward: description
```

Xem chú thích đầu file cấu hình để biết thêm tuỳ chọn (`headers`, `exclude`, `code_pattern`,
`allow_empty`, ...).

### Tìm selector cho trang mới

```bash
python -m giftcode_finder inspect https://example.com/giftcode            # trang HTML thường
python -m giftcode_finder inspect https://example.com/giftcode --render   # trang dùng JavaScript
python -m giftcode_finder inspect <url> --click 'text="Nhận code"'        # bấm nút rồi xem trang gọi API gì
python -m giftcode_finder inspect <url> --grep giftcode                   # tìm chữ trong file JS của trang
```

Lệnh này in các giá trị trông giống giftcode kèm CSS selector của chúng, các URL API và (khi
render) các response JSON mà trang tải về. Trên GitHub, chạy workflow với ô **Chẩn đoán** được
tích (và tham số thêm cho `inspect` nếu cần) để xem kết quả này trong log.

## Chạy trên máy

```bash
pip install -r requirements-dev.txt
python -m giftcode_finder run --dry-run   # chỉ in code, không ghi file
python -m giftcode_finder run             # cập nhật data/, README và dựng web vào _site/
python -m pytest                          # chạy test
```

Mở `_site/index.html` để xem trang web. Nguồn có `render: true` (và `inspect --render`) cần thêm
`pip install playwright && playwright install chromium`.
