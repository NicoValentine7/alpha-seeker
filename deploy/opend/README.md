# OpenD セットアップ

このディレクトリにmoomoo OpenDのLinux版バイナリを配置する。

## 手順

1. https://www.moomoo.com/download/OpenAPI からLinux版OpenDをダウンロード
2. 解凍して以下のファイルをこのディレクトリに配置:
   - `FutuOpenD` (実行バイナリ)
   - `FutuOpenD.xml` (設定ファイル)
3. `FutuOpenD.xml` にmoomooアカウント情報を設定:
   ```xml
   <login_account>あなたのmoomoo ID</login_account>
   <login_pwd_md5>パスワードのMD5ハッシュ</login_pwd_md5>
   ```
4. `chmod +x FutuOpenD` で実行権限を付与

## 注意

- `FutuOpenD` と `FutuOpenD.xml` は `.gitignore` に追加済み（認証情報を含むため）
- パスワードのMD5ハッシュは `echo -n 'your_password' | md5sum` で生成
