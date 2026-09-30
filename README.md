# Lo más buscado hoy

Sitio que se regenera solo cada 30 minutos con las tendencias de Google.

## Puesta en marcha (unos 10 minutos)
1. Creá un repositorio **público** en GitHub y subí todo el contenido de esta carpeta (incluida `.github`).
2. En el repo: **Settings → Pages → Source: GitHub Actions**.
3. En **Actions**, abrí "Actualizar tendencias" y tocá **Run workflow**. Al terminar te da la URL.
4. Dominio propio (opcional): en **Settings → Pages → Custom domain** poné tu dominio y en
   **Settings → Secrets and variables → Actions → Variables** creá `SITE_URL` (ej. `https://tudominio.com`).
5. País: creá la variable `GEO` (AR, MX, ES, CO…). Por defecto es AR.
6. Entrá a Google Search Console, dá de alta el sitio y enviá `sitemap.xml`.

## Importante
- Es la primera vez que corre contra el feed real de Google: si el paso "Generar sitio" falla, mirá el log y avisame.
- Sumá texto propio en `extras/` para los temas de tu nicho.
