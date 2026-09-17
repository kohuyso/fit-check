# 📊 BÁO CÁO TOÀN DIỆN VỀ ARCHIFY (tt-a1i/archify)
**Công cụ Sinh Sơ Đồ Kiến Trúc Hệ Thống Chuẩn Showcase Dành Cho Kỹ Sư & AI Agent**

---

## 📌 1. TỔNG QUAN DỰ ÁN

| Thuộc tính | Chi tiết |
| :--- | :--- |
| **Tên dự án** | **Archify** |
| **Repository** | [https://github.com/tt-a1i/archify](https://github.com/tt-a1i/archify) |
| **Phiên bản hiện tại** | `2.17.0-dev.1` |
| **Mục đích** | Tạo các sơ đồ kiến trúc, tuần tự, quy trình, luồng dữ liệu và vòng đời dưới dạng **file HTML độc lập (Standalone) chứa inline SVG**, có tính tương tác cao, hỗ trợ Dark/Light mode, hiệu ứng dòng chảy (Trace motion), và trích xuất đa định dạng. |
| **Môi trường yêu cầu**| Node.js $\ge$ 18 (Zero heavy dependencies, không cần dựng server backend) |
| **Đối tượng sử dụng** | Software Architects, Tech Leads, DevOps/MLOps Engineers và các **Agent AI Coding** (Antigravity, Cursor, Cline, Copilot). |

---

## 🎯 2. TRIẾT LÝ THIẾT KẾ & ĐIỂM ĐỘT PHÁ CỦA ARCHIFY

Khác với các công cụ tạo sơ đồ truyền thống (Mermaid, PlantUML, Draw.io, Excalidraw), Archify được thiết kế theo tư duy **Agent-Native & Code-First**:

### 1. File HTML Độc Lập Hoàn Toàn (Standalone Single-File Artifact)
* Toàn bộ sơ đồ, mã nguồn JavaScript điều khiển, CSS styling, bộ font chữ, thư viện biểu tượng thương hiệu (Brand Icons) và vector SVG được đóng gói nguyên khối vào **1 file HTML duy nhất** (~700KB).
* **Không phụ thuộc Internet hay CDN**: File mở trực tiếp bằng bất kỳ trình duyệt nào (`file:///...`) ngay cả khi ngắt toàn bộ kết nối mạng.

### 2. Định Dạng Trung Gian Chuẩn Hóa (JSON-IR)
* Thay vì sử dụng cú pháp ngôn ngữ đặc tả dạng text tự do dễ gãy vỡ (như Mermaid DSL), Archify sử dụng **JSON Schema (Draft 2020-12)** nghiêm ngặt.
* Định dạng JSON này giúp các AI Coding Assistant biên soạn có cấu trúc, kiểm tra kiểu dữ liệu (typing), kiểm soát tọa độ, và sửa lỗi tự động với độ chính xác 100%.

### 3. Động Cơ Toán Học Định Tuyến & Rào Cản Thẩm Mỹ (Geometry & Composition Engine)
* **Automatic Port Spread**: Tự động phân bổ cổng kết nối trên các cạnh của node, chống hiện tượng nhiều đường nối chập vào cùng một điểm.
* **Quy tắc tránh cắt chéo (Proper Crossing)**: Nghiêm cấm đường nối cắt ngang qua một node không liên quan (`edge-through-node`).
* **Khoảng cách nhãn (Label Clearance Floor)**: Tự động đo diện tích hộp chữ (bounding box) của từng nhãn nối; nếu nhãn đè lên đường khác hoặc node kế bên, công cụ lập tức báo lỗi và đưa ra tọa độ gợi ý sửa (`labelAt`, `labelDx`, `labelDy`).

### 4. Cam Kết Nguyên Tử & Kiểm Thử Nghiêm Ngặt (Deterministic Delivery)
* Quy trình tạo sơ đồ trải qua 3 bước:
  1. `validate`: Chạy 9 bài kiểm tra hình học và bố cục không gian.
  2. `deliver`: Tạo snapshot nội bộ, render kiểm tra lại, tính mã băm **SHA-256** cho cả file đặc tả và artifact đầu ra, ghi đè nguyên tử (atomic commit).
  3. `visual-check`: Kiểm thử tự động kích thước màn hình trên Headless Chrome ở độ phân giải 1440×900, 1600×1000, 1920×1080 và 2048×1320.

---

## 📐 3. BỘ 5 LOẠI SƠ ĐỒ CHUYÊN SÂU (THE 5 CORE DIAGRAM TYPES)

Archify hỗ trợ trọn vẹn 5 góc nhìn kiến trúc phần mềm tiêu chuẩn:

```
                      ┌──────────────────────────────────────┐
                      │          ARCHIFY ENGINE              │
                      └──────────────────┬───────────────────┘
         ┌───────────────┬───────────────┼───────────────┬───────────────┐
         ▼               ▼               ▼               ▼               ▼
   [Architecture]   [Sequence]      [Workflow]      [Dataflow]      [Lifecycle]
    Kiến trúc       Tuần tự         Quy trình       Luồng dữ liệu   Vòng đời
    hệ thống        gọi hàm         phân làn        chuyển hóa      trạng thái
```

### 1. Architecture Diagram (Sơ Đồ Kiến Trúc Hệ Thống)
* **Vai trò**: Mô tả cảnh quan hệ sinh thái, cấu trúc tầng (Tiers), cụm triển khai (Docker, Kubernetes), ranh giới mạng/bảo mật (Security boundaries), và các dịch vụ ngoại vi.
* **Tính năng đặc thù**: Hỗ trợ gắn **Brand Marks** chính hãng (FastAPI, Redis, PostgreSQL, Gemini, React, Docker...), nhãn thẻ (Tag), nhóm ranh giới (`region`, `security-group`).

### 2. Sequence Diagram (Sơ Đồ Tuần Tự)
* **Vai trò**: Trình bày thứ tự giao tiếp theo trục thời gian giữa các thành phần phần mềm.
* **Tính năng đặc thù**: Hỗ trợ phân đoạn thời gian (Segments), thanh kích hoạt (Activation bars), các biến thể thông điệp mang ngữ nghĩa (`emphasis`, `security`, `return`, `dashed`), và chế độ dàn đều thông minh `column_fit: "spread"`.

### 3. Workflow Diagram (Sơ Đồ Quy Trình Công Việc)
* **Vai trò**: Trực quan hóa quy trình xử lý qua nhiều làn trách nhiệm (Swimlanes), các giai đoạn logic (Phases) và luồng chính (Main Path).
* **Tính năng đặc thù**: Phân biệt rạch ròi luồng xử lý thành công (Happy Path), luồng kiểm duyệt bảo mật (Policy Gate) và luồng phục hồi lỗi (Exception / Recovery Path).

### 4. Data Flow Diagram (Sơ Đồ Luồng Dữ Liệu)
* **Vai trò**: Thể hiện chu trình dữ liệu biến đổi qua 5 tầng: **Sources $\rightarrow$ Ingest $\rightarrow$ Process/Transform $\rightarrow$ Store $\rightarrow$ Consume**.
* **Tính năng đặc thù**: Phân loại nhãn dữ liệu theo cấp độ bảo mật/ngữ nghĩa (`raw payload`, `encrypted PII`, `feature vectors`, `dense embeddings`).

### 5. Lifecycle Diagram (Sơ Đồ Vòng Đời Trạng Thái)
* **Vai trò**: Theo dõi vòng đời thực thể từ khởi tạo (Start), xử lý (Active), chờ/tạm hoãn (Waiting), quyết định (Decision) đến thành công (Success) hoặc kết thúc/hủy (Terminal).
* **Tính năng đặc thù**: Hỗ trợ kiểm tra đường hoàn trả bắt buộc đối với các trạng thái lỗi có thể thử lại (`retryable failure`).

---

## 💻 4. TÍNH NĂNG TƯƠNG TÁC ĐỈNH CAO (VIEWER RUNTIME)

Một sơ đồ do Archify tạo ra không phải là hình ảnh chết, mà là một **Single-Page Application (SPA)** thu nhỏ:

### 1. Khám Phá Trực Quan (Interactive Exploration)
* **Phóng to / Thu nhỏ & Di chuyển (Pan & Zoom)**: Điều khiển mượt mà bằng chuột hoặc trackpad.
* **Độ sâu đọc thông minh (Reading Depth)**:
  * Tự động điều chỉnh: Mức `READ` ở 100%, tự mở bung chi tiết `FULL` khi zoom lên $\ge$ 175%, và chuyển sang chế độ bản đồ `MAP` khi thu nhỏ.
* **Radar Điều Hướng (Semantic Radar)**: Bản đồ thu nhỏ (Minimap) hiển thị góc nhìn hiện tại so với toàn thể đồ thị.
* **Tìm Kiếm Linh Hoạt (Node Finder)**: Nhấn phím nóng để tìm nhanh bất kỳ Component hoặc ID nào trên canvas.

### 2. Kể Chuyện Theo Chương (Guided Views & Story Mode)
* Cho phép tác giả cấu hình `meta.views` tối đa 5 chương nghiệp vụ.
* Người xem chỉ cần bấm chuyển chương: Canvas sẽ tự động lia camera (Camera Follow), tập trung làm nổi bật các node trong chương và làm mờ các thành phần không liên quan.

### 3. Truy Vết Quan Hệ & Thăm Dò Đường Đi (Semantic Lens & Route Probe)
* **Semantic Passport**: Nhấp vào node bất kỳ để mở bảng tra cứu toàn bộ quan hệ đầu vào (Upstream) và đầu ra (Downstream), kèm đường dẫn Deep Link (ví dụ: `#focus=postgres`).
* **Route Probe**: Nhấp chọn 2 node bất kỳ, Viewer sẽ tự động vẽ luồng đi thực tế xuyên qua các directed edge nối giữa chúng.

### 4. Hiệu Ứng Dòng Chảy & Thuyết Trình (Motion & Presentation)
* **Trace Animation**: Kích hoạt hoạt ảnh các luồng dữ liệu chạy dọc theo các đường nối (`data-stream motion`).
* **Presentation Stage (`?present=1`)**: Ẩn các thanh công cụ, mở rộng không gian tối đa phục vụ trình chiếu slide/hội nghị.
* **Chế độ nhúng (`?embed=1`)**: Nhúng sơ đồ vào website nội bộ, Wiki hoặc Notion mà không lộ viền công cụ.

### 5. Xuất File Đa Định Dạng (Canonical Exports)
Ngay trên thanh công cụ, người dùng có thể tải về:
* **Ảnh PNG Full-HD / 4K** (toàn bộ canvas không bị cắt xén).
* **Dual-theme SVG**: File vector giữ nguyên độ sắc nét khi phóng to vô hạn, tự động đổi màu theo Dark/Light mode.
* **Ảnh WebP / JPEG**.
* **Video WebM**: Ghi hình trực tiếp hiệu ứng chuyển động dòng chảy để đưa vào Slide.
* **Share Card (1200×630 PNG)**: Tỷ lệ chuẩn vàng để chèn vào `README.md`, thông cáo PR, hoặc bài đăng mạng xã hội.

---

## ⚖️ 5. SO SÁNH ARCHIFY VỚI CÁC CÔNG CỤ HIỆN CÓ

| Tiêu chí | Archify (`tt-a1i/archify`) | Mermaid.js | PlantUML | Draw.io / Excalidraw |
| :--- | :--- | :--- | :--- | :--- |
| **Định dạng đầu ra** | **Interactive Standalone HTML** | SVG / Canvas tĩnh | PNG / SVG tĩnh | XML / PNG tĩnh |
| **Độ tin cậy & Kiểm thử** | **Tuyệt đối** (Toán học layout, 9 bài test artifact, checksum SHA-256) | Kém (Hay lỗi cú pháp, chữ đè đường nối) | Trung bình (Cần Java & Graphviz) | Thủ công (Kéo thả bằng tay) |
| **Khả năng tương tác** | **Đầy đủ** (Zoom/Pan, Search, Story Views, Route Probe, Trace Animation) | Rất hạn chế (Chỉ hover cơ bản) | Không có (Ảnh tĩnh) | Thủ công khi mở app |
| **Tối ưu cho AI Agent** | **Xuất sắc** (Chuẩn JSON Schema, chẩn đoán lỗi kèm tọa độ sửa `labelAt`) | Khá (Agent viết DSL dễ sai cú pháp) | Kém (Cần server Java để render) | Không khả thi (Agent khó chỉnh tọa độ kéo thả) |
| **Thương hiệu & Preset** | **Có sẵn 100+ SVG Brand Marks** (FastAPI, Redis, Gemini, Docker...) | Không có | Cần import plugin ngoài | Kéo thả icon thủ công |
| **Tự chủ môi trường** | **Chạy offline 100% qua Node.js**, 0 phụ thuộc CDN | Cần script CDN hoặc bundle lớn | Cần máy ảo Java + Graphviz | Cần mở web app hoặc Desktop |

---

## 🛠️ 6. HƯỚNG DẪN CÀI ĐẶT & SỬ DỤNG

### 1. Cài đặt vào môi trường Agent
```bash
# Cài đặt toàn cục cho Agent CLI
npx skills add tt-a1i/archify -g
```

### 2. Kiểm tra trạng thái hệ thống
```bash
node ~/.agents/skills/archify/bin/archify.mjs doctor
```

### 3. Quy trình làm việc tiêu chuẩn (3 Bước)
1. **Biên soạn file cấu hình JSON**:
   * Chọn 1 trong 5 loại: `architecture`, `sequence`, `workflow`, `dataflow`, `lifecycle`.
2. **Kiểm tra hợp lệ & Hình học (Validate)**:
   ```bash
   node bin/archify.mjs validate <type> input.json --quality showcase
   ```
   *Nếu có lỗi va chạm chữ, CLI sẽ trả về tọa độ chính xác cần sửa (ví dụ: `labelAt: [638, 144]`).*
3. **Phát hành file HTML (Deliver)**:
   ```bash
   node bin/archify.mjs deliver <type> input.json output.html --quality showcase --json
   ```

---

## 💡 7. KẾT LUẬN & ĐÁNH GIÁ

**Archify** đại diện cho **thế hệ công cụ Diagramming 2.0**:
1. **Thay đổi cuộc chơi về tài liệu hóa phần mềm**: Biến các bản vẽ kiến trúc vốn nhanh chóng lỗi thời thành các **Artifact sống**, có thể kiểm soát phiên bản bằng Git, tương tác như một trang web và thẩm mỹ ngang tầm các bài thuyết trình công nghệ quốc tế.
2. **Cánh tay đắc lực cho AI Coding**: Cung cấp giao thức JSON chặt chẽ giúp Agent hiểu sâu sắc cấu trúc dự án, tự vẽ, tự bắt lỗi hình học và tự bàn giao kết quả với chất lượng hoàn hảo.
3. **Giá trị ứng dụng trực tiếp trong dự án FitCheck**: Đã chứng minh hiệu quả vượt trội khi xuất thành công toàn bộ 5 sơ đồ hệ thống: [Architecture](file:///Users/Astar/Python/fitcheck-backend/docs/architecture-fitcheck.html), [Sequence](file:///Users/Astar/Python/fitcheck-backend/docs/sequence-fitcheck.html), [Workflow](file:///Users/Astar/Python/fitcheck-backend/docs/workflow-fitcheck.html), [Data Flow](file:///Users/Astar/Python/fitcheck-backend/docs/dataflow-fitcheck.html) và [Lifecycle](file:///Users/Astar/Python/fitcheck-backend/docs/lifecycle-fitcheck.html).
