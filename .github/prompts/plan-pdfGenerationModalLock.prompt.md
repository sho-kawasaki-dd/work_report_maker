## Plan: PDF生成中のモーダル進捗表示

GUI の最終 PDF 生成を同期呼び出しからバックグラウンド実行へ切り替え、生成中はモーダル進捗ダイアログで「報告書PDFを生成中です...」を表示してウィザード操作をロックする。既存の画像読み込み実装と同じ QThread + QObject worker パターンを再利用し、進捗バーは不定表示、ラベルは QTimer でドット数を変える簡易アニメーションにする。加えて、進行中ダイアログには中断ボタンを設け、生成前の編集状態が失われないよう、一時データやメモリの cleanup は生成完了が確定するまで遅延させる方針で進める。

**Steps**
1. PDF 生成フローの非同期化設計を固める。ReportWizard.accept() で保存先確定と payload 構築までは UI スレッドで行い、その後の generate_full_report(...) だけを worker に移す。これは既存の photo import と同様に UI 凍結を防ぐためで、payload 構築失敗、PDF 生成失敗、中断要求を分離して扱える。
2. PDF 生成用 controller/worker を追加する。src/work_report_maker/gui 配下の既存責務に合わせて GUI 層へ新しい helper もしくは main_window.py 内 private class を置き、worker は finished / error / cancelled の signal を返せるようにする。QThread, worker, progress dialog, timer のライフサイクルは controller に閉じ込め、中断要求を安全に伝える入口も持たせる。*この手順は 3,4 の前提*
3. 進行中ダイアログをモーダル化してアニメーションを付ける。QProgressDialog を 0-0 の不定進捗、WindowModal 以上のモーダル設定で生成し、ラベル初期値を「報告書PDFを生成中です...」にする。QTimer で末尾のドットを 1-3 個で循環させるか、短い記号列を回す形にして、簡単な進行感を出す。*depends on 2*
4. 進行中ダイアログへ中断ボタンを追加する。中断ボタン押下時は controller 経由で worker に停止要求を送り、可能なら安全に処理を止め、少なくとも完了後の結果反映と cleanup を保留する。中断後はウィザードを閉じず、生成前の編集状態のまま再試行できることを優先する。*depends on 2,3*
5. ReportWizard の操作ロックを統合する。accept() は worker 開始後すぐ return し、成功時だけ success ダイアログ表示と QWizard.accept() を行う。生成中フラグまたは controller.is_running() を参照して、再度 accept() されないようにし、closeEvent() でも PDF 生成中なら閉じる操作を無効化して案内メッセージを出す。既存の stop_active_photo_operations() 集約と同じ考え方で PDF 生成状態も扱えるようにする。*depends on 2,3,4*
6. cleanup の責務を結果別に整理する。現状は accept() の finally で photo tmp dir を掃除しているが、非同期化後は生成前の編集状態を守るため、少なくとも PDF 生成中には cleanup しない。成功時は完了ハンドラで cleanup し、中断時や失敗時は編集内容を保持したまま再実行できるよう、一時データや関連メモリを残すか、再利用可能な形で保持する。*depends on 5*
7. GUI テストを更新・追加する。既存の tests/gui/test_photo_description_page.py の PDF 生成完了系テストは同期前提なので、worker/controller の開始確認、完了時の成功メッセージ、保存ダイアログキャンセル時の非開始、中断ボタン押下時の停止要求、生成中 closeEvent 抑止を確認する形へ広げる。必要なら controller を差し替え可能にしてテスト容易性を確保する。*depends on 4,6*
8. 回帰確認を行う。既存の photo import/arrange 側の closeEvent 挙動を壊していないこと、PDF 生成失敗時や中断時にウィザードが閉じず再実行可能なこと、成功時だけ cleanup が行われることを確認する。*depends on 7*

**Relevant files**
- c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\gui\main_window.py — ReportWizard.accept(), closeEvent(), _cleanup_photo_tmp_dir() を非同期フローへ変更する中心箇所
- c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\gui\pages\photo_import_operation.py — QThread + QProgressDialog の既存パターン。signal 接続、cleanup、終了ハンドリングの参照元
- c:\Users\tohbo\python_programs\work_report_maker\src\work_report_maker\services\pdf_generator.py — worker から呼ばれる生成本体。GUI から直接の同期呼び出しをやめても API はそのまま再利用可能
- c:\Users\tohbo\python_programs\work_report_maker\tests\gui\test_photo_description_page.py — accept() まわりの既存テスト更新対象
- c:\Users\tohbo\python_programs\work_report_maker\tests\gui\test_report_wizard_integration.py — closeEvent の統合挙動を追加確認する候補

**Verification**
1. GUI テストで、保存ダイアログ決定後に PDF 生成 controller が開始され、即時に完了メッセージではなく進捗ダイアログが出ることを確認する。
2. GUI テストで、進捗ダイアログに中断ボタンが表示され、押下時に停止要求が controller / worker へ伝播することを確認する。
3. GUI テストで、worker 完了 signal 後にだけ「PDF 生成完了」メッセージと QWizard.accept() 呼び出しが発生し、そのタイミングで cleanup が走ることを確認する。
4. GUI テストで、worker error signal 時は「PDF 生成エラー」が表示され、ウィザードは閉じず、編集状態と再試行に必要なデータが保持されることを確認する。
5. GUI テストで、中断完了後はウィザードが閉じず、入力済み内容が保持され、再実行可能であることを確認する。
6. GUI テストで、PDF 生成中の closeEvent が ignore され、ユーザー向け案内メッセージが表示されることを確認する。
7. 必要なら pytest で tests/gui/test_photo_description_page.py と tests/gui/test_report_wizard_integration.py を実行し、既存の保存ダイアログキャンセルケースが維持されることを確認する。

**Decisions**
- 進捗表示は割合付きではなく不定進捗にする。現状の generate_full_report(...) から細粒度進捗は取れないため、無理に割合を出さない。
- 進行中ダイアログには中断ボタンを含める。ただし停止方法は安全性優先で設計し、即時 kill よりも「停止要求を出して結果反映を抑止する」形を第一候補にする。
- cleanup は生成中には行わず、成功完了時に実施する。失敗時や中断時は生成前の編集状態を維持できることを優先する。
- アニメーションはダイアログ文言の簡易更新に限定し、新規の複雑なカスタムウィジェットは導入しない。

**Further Considerations**
1. controller の配置先は main_window.py 内 private class でも成立するが、再利用性とテスト性を優先するなら gui/report_generation_operation.py のような専用モジュールへ分離する方が保守しやすい。
2. WeasyPrint の PDF 書き出し中断が即時に止められない場合は、「中断要求済み」状態を UI に示し、完了後に保存成功扱いしない設計が現実的かを検討する。
3. closeEvent のメッセージは既存の画像処理停止メッセージと文体を合わせると UI の一貫性が保ちやすい。
