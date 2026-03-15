PDF生成成功後の自動終了は、[src/work_report_maker/gui/main_window.py](src/work_report_maker/gui/main_window.py#L252) の成功ハンドラで [QWizard.accept 相当の終了処理](src/work_report_maker/gui/main_window.py#L255) を無条件に呼んでいるのが原因です。一方で、生成スレッド側の解放は [src/work_report_maker/gui/report_generation_operation.py](src/work_report_maker/gui/report_generation_operation.py#L176) で先に完了しており、写真用の一時ディレクトリは [src/work_report_maker/gui/main_window.py](src/work_report_maker/gui/main_window.py#L252) から明示解放されています。したがって、終了するかどうかの選択肢は成功後UIの分岐として追加しつつ、クリーンアップは終了有無と独立して必ず走らせる方針が妥当です.

1. [src/work_report_maker/gui/preset_manager.py](src/work_report_maker/gui/preset_manager.py) の PDF 出力設定JSONを拡張し、既存の保存先フォルダ設定に加えて「PDF生成後に閉じる」設定を同居させます。既存ファイルが保存先だけを持っていても読める後方互換を維持します。
2. [src/work_report_maker/gui/pages/project_name_page.py](src/work_report_maker/gui/pages/project_name_page.py) にトグルを追加します。初期値は「終了しない」で、ページ表示時に永続設定を読み込み、ユーザー変更を保存できるようにします。
3. [src/work_report_maker/gui/main_window.py](src/work_report_maker/gui/main_window.py) の成功処理を、まず一時ディレクトリを解放し、その後に成功メッセージを表示し、最後に設定が有効な場合だけ終了する分岐へ変更します。これで終了しない場合でも再生成可能な状態へ戻せます。
4. 失敗時と中断時の既存仕様は維持します。つまり、一時ディレクトリは成功時のみ解放し、失敗時と中断時は再実行のため保持し、次回生成前の既存掃除ロジックをそのまま使います。
5. GUIテストを更新します。[tests/gui/test_report_wizard_integration.py](tests/gui/test_report_wizard_integration.py) では、初期値が終了しないこと、トグルOFFでは成功後も終了しないこと、トグルONでは終了すること、設定変更が保存されることを追加します。[tests/gui/test_photo_description_page.py](tests/gui/test_photo_description_page.py) では、成功時の一時ディレクトリ解放と終了挙動の前提変更に追従します。

## Relevant files

- [src/work_report_maker/gui/preset_manager.py](src/work_report_maker/gui/preset_manager.py)
- [src/work_report_maker/gui/pages/project_name_page.py](src/work_report_maker/gui/pages/project_name_page.py)
- [src/work_report_maker/gui/main_window.py](src/work_report_maker/gui/main_window.py)
- [src/work_report_maker/gui/report_generation_operation.py](src/work_report_maker/gui/report_generation_operation.py)
- [tests/gui/test_report_wizard_integration.py](tests/gui/test_report_wizard_integration.py)
- [tests/gui/test_photo_description_page.py](tests/gui/test_photo_description_page.py)

## Verification

1. 成功時にトグルOFFならウィザードが閉じず、一時ディレクトリだけは解放されることを確認します。
2. 成功時にトグルONなら従来どおり終了することを確認します。
3. キャンセル時と失敗時に編集状態保持の挙動が変わっていないことを確認します。
4. アプリ再起動後もトグル設定と保存先フォルダ設定の両方が保持されることを確認します。
