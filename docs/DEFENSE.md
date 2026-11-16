# Как показать StudyMate

## Подготовка

Запустите `start.command`, откройте главную. Даты и язык — по Алматы. Выберите интервал, который ещё не занят. Демонстрационные роли находятся в «Режиме защиты» в верхней полосе; обычный посетитель может смотреть каталог без входа и зарегистрироваться по email.

## Показ за 3–4 минуты

1. Начните с главной: журнальная типографика, локальный коллаж, один ясный вопрос — с какой темой нужна помощь.
2. Аликхан: выберите SQL JOIN, бюджет 3000 ₸, онлайн, дедлайн после доступного времени. Нажмите поиск. Измените бюджет: результаты нельзя выбрать, пока новые условия не применены. Верните 3000.
3. Откройте Аяулым, выберите свободное время, напишите конкретный вопрос. Покажите страницу новой встречи. Можно пройти три вопроса до встречи и сохранить личную заметку.
4. Переключитесь на Аяулым. В «Моих учениках» откройте запрос. Для онлайн-встречи укажите реальную HTTPS-ссылку, которую вы подготовили для защиты; для очной — аудиторию. Подтвердите. Добавьте материалы. В календаре время теперь занято.
5. Нажмите «Демо: встреча завершена». Объясните, что это ускорение показа; в обычном режиме требуется дождаться окончания встречи.
6. Вернитесь к Аликхану, откройте встречу и подтвердите завершение. Пройдите другие три вопроса, покажите сравнение результатов, оставьте отзыв и откройте зачётку.
7. Команда: приостановите анкету и покажите, что личная доступность ментора её не включает. Верните доступ. Отметьте, что метрики здесь основаны на вымышленных данных.

Не переходите по примерной ссылке `example.org` как по настоящей видеовстрече. StudyMate хранит место встречи, но не создаёт звонки.

## Новое в 2.2: ещё 2–3 минуты (всего не больше 6)

Демоданные уже подготовлены: у Аяулым есть групповое занятие «SQL JOIN, 4 места», где записан Ерлан, и недельная серия интервалов. У Аликхана в избранном Амина и запрос в листе ожидания. В заявке Ерлана к Аяулым есть короткая переписка.

1. **Поиск и рекомендации (30 с).** Аликхан → «Мои занятия»: блок «Вам может подойти» показывает причину каждой рекомендации. В каталоге выберите «Любая тема» и введите слово из анкеты, например «спокойн». Переключите сортировку «Выше рейтинг» и объясните поправку на число отзывов. Нажмите звёздочку.
2. **Групповое занятие (40 с).** Откройте Аяулым из каталога с дедлайном на несколько дней вперёд. Пунктирная кнопка — группа: «занято 1 из 4 · 1 200 ₸ за место». Запишитесь: место подтверждается сразу, на странице встречи видно «Группа · 2 из 4» и участников.
3. **Чат в реальном времени (40 с).** Откройте вторую вкладку (у каждой вкладки своя сессия) и войдите Аяулым. Откройте ту же встречу. Аликхан пишет сообщение, и у Аяулым оно появляется без перезагрузки, а у Аликхана — «Прочитано».
4. **Лист ожидания (20 с).** Во вкладке Аяулым → «Календарь» добавьте время в окне запроса Аликхана. У Аликхана загорается колокольчик: «Появилось время по теме…». Клик ведёт в анкету.
5. **Перенос и календарь (30 с).** На встрече один на один нажмите «Предложить другое время», выберите время. Другой участник нажимает «Перенести»: id встречи, заметки и переписка остались. «Добавить в календарь (.ics)» скачивает файл для Apple или Google Calendar.

## English speech

StudyMate helps students find someone on their own campus who has already passed the course they are struggling with. The idea is a short session about one specific topic, rather than a long tutoring course.

I can browse the mentors without signing in. Here I choose SQL joins, my budget, language and the time before my deadline. The site checks these conditions again when I send the request, so an outdated result cannot create an invalid booking.

The mentor receives the request in their own account. They add a meeting link or a campus location before confirming. Both students then have one lesson page with the question, materials and separate private notes.

After the session, the mentor marks it finished and the student confirms that it happened. Only then can the student leave a review. The questions before and after the meeting are different. They help show a change in a few specific skills; they do not prove that the student has mastered the whole subject.

The design takes its cues from a campus magazine: paper, editorial type, handwritten details and a custom collage. The application runs on this computer and saves its data in a local database. Payments are only simulated. The next step would be a small campus pilot to measure how quickly students find help, whether sessions are useful and whether they book again.

## Возможные вопросы

**Why not just use ChatGPT?** A peer can explain the exact course, understand the local assignments and work through a student's attempt. AI and free study groups remain real alternatives.

**What is the business model?** The example uses a 15% commission on a session. No money is collected in this prototype. A pilot would need to test price and mentor availability before claiming a viable business.

**Can a mentor invent reviews?** Reviews require a completed booking and belong to its student. This reduces arbitrary reviews, but genuine campus identity would still need verification in a public service.

**What did you actually test?** Automated checks cover booking conflicts, access rights, accounts, notifications, notes and progression. The main student-to-mentor flow was also clicked through in the browser. See VERIFICATION.md for the precise scope.

**Why SSE and not WebSockets?** Updates flow one way, from the server to the browser. Server-Sent Events work over plain HTTP, reconnect easily and need no extra library. The stream carries only a hint like "this lesson changed"; the page then reloads that data through the normal API. So a dropped connection never loses anything, and the session token never appears in a URL: the page exchanges it for a 30-second single-use ticket.

**How do you avoid selling the last group seat twice?** Every booking runs in a serialized SQLite write transaction and checks the free seats first. Below that, a database trigger aborts any insert or status change that would exceed the slot capacity, even if application code were wrong. A test lets five threads compete for one seat; exactly one wins.

**Why recommendations without machine learning?** We have too little data for a model to be meaningful, and students should understand why a mentor is suggested. It is a small set of weighted rules (a weak quiz topic, interests, favorites, a good previous session, verification, a rating adjusted for the number of reviews), and every suggestion shows its reasons.

**What is missing?** Email verification and account recovery, real payments, built-in video and public hosting. This is a working local website prototype.
