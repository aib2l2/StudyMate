# StudyMate: campus edition

Визуальная идея — студенческий журнал и учебный блокнот. Кремовая бумага, чернильный текст, рыжие пометки и синий цвет записей. Крупная антиква и курсив в заголовках сочетаются с простым основным шрифтом и маленькими редакционными подписями. Системные Georgia/Times и Arial работают без загрузки шрифтов.

Вместо одинаковых закруглённых карточек — линейки, списки людей, заметка с поиском, лист встречи и зачётка со штампами. На широком экране главная делится между крупным текстом и коллажем, каталог — между условиями и людьми. На телефоне блоки складываются в одну колонку, навигация открывается кнопкой.

Основная палитра: бумага #f7f4ed, чернила #242a2a, рыжий #bd472a, синий #304c82, серый для вторичного текста #6b6c65. В версии 2.1 рыжий (был #cc4e2d) и серый (был #74756e) чуть затемнены, чтобы текст проходил WCAG AA (не меньше 4,5:1) на бумаге. Есть отдельные значения для тёмной темы. Учитывается системное предпочтение уменьшенного движения.

## Авторская иллюстрация

Режим: новая генерация встроенным imagegen, непрозрачный фон, без референсов. Применение: главная страница сайта. Файл проекта: `frontend/public/images/campus-editorial.png`; тот же файл копируется Vite в `frontend/dist/images/`. Это вымышленная сцена, а не фотографии пользователей StudyMate.

Prompt:

> Original handmade mixed-media college magazine collage on warm ivory paper. Two Central Asian university students, a woman and a man around twenty, discussing a notebook at a study table. Photographic cutout people with flat rust-orange and ink-navy paper geometry, thin hand-drawn blue pencil loops and graph paper details, a notebook, a blue book and an orange pencil. Square composition that can sit next to large serif typography. Tactile paper edges, understated shadows, warm natural light, editorial art direction. No letters, text, logos, UI or watermark. Avoid generic 3D SaaS illustration, gradients, glowing orbs and mascots.

Локальные буквы AI/TU поверх коллажа добавлены средствами интерфейса; они не являются логотипом университета. Иллюстрация создана специально для этого проекта. Иконки — Lucide из установленной зависимости.
