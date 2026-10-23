# 🎁 GiftCode Finder

Tự động lấy giftcode game từ các trang web, cập nhật mỗi giờ bằng GitHub Actions.
Mở link là có code, bấm vào code là sao chép.

**👉 Xem code: https://phanquochuyiuh.github.io/GiftCode-Finder/**

(Danh sách bên dưới cũng tự cập nhật, dùng được ngay cả khi chưa bật trang web.)

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
3. Kết quả gộp với lịch sử trong [`data/codes.json`](data/codes.json): code mới được ghi
   ngày phát hiện, code bị gỡ khỏi trang nguồn được chuyển sang mục "code cũ".
4. Trang web được dựng lại và đăng lên GitHub Pages; bảng code ở README này cũng được
   cập nhật (chỉ commit khi danh sách code thay đổi).

Nếu một trang nguồn bị lỗi (sập, đổi giao diện), code cũ của nguồn đó vẫn được giữ và trang
web hiện cảnh báo, chứ không xoá sạch danh sách.

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

## Thêm game hoặc trang nguồn

Mọi thứ nằm trong [`config/sources.yaml`](config/sources.yaml). Một game có thể có nhiều
nguồn; code trùng giữa các nguồn được gộp lại.

**Game khác trên Gzone** — chỉ cần đổi số id trong link:

```yaml
  - id: ten-game
    name: Tên Game
    sources:
      - id: gzone
        name: Gzone (zoneplay.vn)
        type: zoneplay
        url: https://zoneplay.vn/care/game/<id>
```

**Trang bất kỳ, lấy bằng CSS selector:**

```yaml
      - id: fanpage
        name: Trang tin game
        type: html
        url: https://example.com/giftcode
        item: ".giftcode-item"      # khối chứa một code
        code: ".code"               # phần tử chứa chữ code (trong item)
        reward: ".reward"           # phần thưởng (tuỳ chọn)
        expires: ".expired"         # hạn dùng (tuỳ chọn)
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

Xem chú thích đầu file cấu hình để biết thêm tuỳ chọn (`headers`, `exclude`,
`code_pattern`, `allow_empty`, ...).

### Tìm selector cho trang mới

```bash
python -m giftcode_finder inspect https://example.com/giftcode           # trang HTML thường
python -m giftcode_finder inspect https://example.com/giftcode --render  # trang dùng JavaScript
```

Lệnh này in các giá trị trông giống giftcode kèm CSS selector của chúng, các URL API và
(với `--render`) các response JSON mà trang tải về. Trên GitHub, chạy workflow với tuỳ chọn
**Chẩn đoán** để xem kết quả này cho mọi nguồn trong log.

## Chạy trên máy

```bash
pip install -r requirements-dev.txt
python -m giftcode_finder run --dry-run   # chỉ in code, không ghi file
python -m giftcode_finder run             # cập nhật data/, README và dựng web vào _site/
python -m pytest                          # chạy test
```

Mở `_site/index.html` để xem trang web. Nguồn có `render: true` cần thêm
`pip install playwright && playwright install chromium`.
