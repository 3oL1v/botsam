# Деплой на Oracle Cloud Always Free (24/7, бесплатно, постоянный домен)

Результат: 3 dry-run бота + Mini App работают в облаке круглосуточно, ПК держать
включённым не нужно. Постоянный HTTPS-адрес вида `https://твоёимя.duckdns.org`.

> Всё в dry-run. Реальная торговля не включается. Карта Oracle нужна только для
> верификации при регистрации — ресурсы Always Free никогда не тарифицируются.

---

## 1. Аккаунт Oracle Cloud
1. https://www.oracle.com/cloud/free/ → Start for free.
2. Регион (Home Region) выбери **Singapore** или **Tokyo** — важно из-за геоблока
   Binance (EU/US дата-центры он режет ошибкой 451). Сменить регион потом нельзя.
3. Пройди верификацию (телефон + карта; списаний по Always Free нет).

## 2. Создать ВМ (ARM Ampere, Always Free)
Compute → Instances → Create instance:
- Image: **Ubuntu 22.04**.
- Shape: **VM.Standard.A1.Flex** (это Always Free ARM). Поставь **2 OCPU / 12 GB**
  (хватает с запасом; бесплатный лимит — до 4 OCPU / 24 GB).
- Networking: оставь публичный IP (Assign public IPv4).
- SSH: загрузи свой публичный ключ (или сгенерируй пару и скачай приватный).
- Create. Запомни **публичный IP**.

### 2.1 Открыть порты 80/443 (Security List)
Networking → Virtual Cloud Networks → твоя VCN → Security Lists → Default →
Add Ingress Rules (дважды):
- Source `0.0.0.0/0`, IP Protocol TCP, Destination Port **80**.
- Source `0.0.0.0/0`, IP Protocol TCP, Destination Port **443**.

## 3. Постоянный домен DuckDNS (бесплатно, без карты)
1. https://www.duckdns.org → войти (Google/GitHub).
2. Придумай поддомен, напр. `botsam`, нажми add domain → получишь
   `botsam.duckdns.org`.
3. В поле current ip впиши **публичный IP твоей ВМ** → update.
   (IP у Oracle статичный, пока инстанс жив; менять обычно не нужно.)

## 4. Подключиться и поставить Docker
```bash
ssh ubuntu@ПУБЛИЧНЫЙ_IP

# Docker + compose
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu
# Переподключись, чтобы группа применилась:
exit
ssh ubuntu@ПУБЛИЧНЫЙ_IP

# Открыть порты в iptables ВМ (Oracle Ubuntu по умолчанию пускает только 22!)
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

## 5. Забрать проект и запустить
```bash
git clone https://github.com/3oL1v/botsam.git
cd botsam

# .env с токеном и доменом
cat > .env <<'EOF'
MINIAPP_ACCESS_TOKEN=ВАШ_ТОКЕН
DOMAIN=botsam.duckdns.org
EOF

docker compose up -d --build
```
Первый build на ARM займёт несколько минут. Caddy сам получит HTTPS-сертификат
для домена (нужно, чтобы DuckDNS уже указывал на IP и порт 80 был открыт).

## 6. Проверка
```bash
docker compose ps
docker compose logs -f bots | grep -E "starting|heartbeat|451|markets"
```
В браузере / Telegram:
- Mini App: `https://botsam.duckdns.org/miniapp?access=ВАШ_ТОКЕН`
- Health:   `https://botsam.duckdns.org/api/health?access=ВАШ_ТОКЕН`

`/api/health` должен показать 3 бота `state: running`, `dry_run: true`.

## 7. Если Binance геоблок (451 / Could not load markets)
Сингапур/Токио обычно проходят. Если всё же режет — пересоздай ВМ в другом
азиатском регионе. (Это та же проблема, что валила Railway EU.)

## Управление
```bash
docker compose restart bots     # перезапустить ботов
docker compose down             # остановить
docker compose up -d --build    # обновить после git pull
docker compose logs -f bots     # логи
```
Контейнеры с `restart: unless-stopped` сами поднимутся после перезагрузки ВМ.
