# Probe serial redaction of the evidence

The debug probe used for the physical runs has a serial number. It is a personal identifier of the
maintainer's equipment and was removed from the committed evidence. Every occurrence of the serial
(as the J-Link serial and as the USB serial with leading zeros) in the files listed below was
replaced by the text `<probe-serial>`. No other byte of these files changed. In particular every
measurement, time, address, count and result is unchanged.

Eight empty lock files were named after the serial. They were renamed to `evkb-probe-serial.lock`
(a file name cannot hold `<` and `>` on every platform). Their content, the empty file, is unchanged, so
their SHA-256 is the same as before.

## How the digests stay consistent

- The three `SHA256SUMS.tsv` files of the networking runs keep the digest of the file as it was
  recorded in `original_sha256`, hold the digest of the committed file in `committed_sha256`, and
  use the state `redacted` for each file that changed (the same state that recorded the earlier
  replacement of absolute paths). For the lock files only the `path` column changed.
- Digests that a run recorded about its own inputs, such as `plan_sha256` and `approval_sha256` in the
  `inputs.json` files and in the run plans, and the `sha256` fields of `m5-physical-preparation.json`
  and `m5-physical-integration.json`, describe the files as they were at run time. They are kept
  unchanged. They match the `original_sha256` column or the table below, not the committed copy.
- Directories without a `SHA256SUMS.tsv` are covered by the table below.

## Files changed

`original_sha256` is the digest before the replacement and `redacted_sha256` the digest of the
committed file. `count` is the number of replacements in the file.

| path | original_sha256 | redacted_sha256 | count |
| --- | --- | --- | --- |
| `microsd-card-states-stack/blank-restore.log` | `362ea40ff0876ed6cc0593be08006746e90f52ecde6223ac4aa2d855b162c11d` | `f2b89636c51ee6bc5525ff22cdf1ac01a271338bcd69684e955b362e612127c4` | 1 |
| `microsd-card-states-stack/layout-flash.log` | `12a936ab7d03a1f484b6ea1f5a4bebd20b18eb6de0bc843321da312513886097` | `45ac292899f17fd37c49e8cac43610a38eeb8e3641f4298fcc25c608f0822638` | 1 |
| `microsd-card-states-stack/layout-preflight.log` | `d4eae9444cd30af22addff5507e53aef803c85892e40f9a6b5f12a7a3b298948` | `d6a48c7cfde30c5a65b3b3074c788e5783ff0f4ddd5adedd397de7955c42dc0c` | 1 |
| `microsd-card-states-stack/layout-reset.log` | `e14c29ec6db34b0e09f30bd5766753e5b5894a506eaea5f41e6d0fef344d11f7` | `c282c6c8a0b172909c92feb0b33edd83fe90f313acd8fee827ce556252b9cfbb` | 1 |
| `microsd-card-states-stack/layout-restore.log` | `e3d99926f7d9ed3d695ac78e765a2c8300d90d8c9110c073f7b648636a242e2b` | `fcd9b09f74fdcd67e28707eb4bb3c33602f88a8e220cdc401e52190f61ee2ed5` | 1 |
| `microsd-card-states-stack/removal-control-flash.log` | `5c93f630674a6e95ba2fc90a9be4bbadba416dc14802748ef1bcb4ab1a9791e5` | `d9b71c3a27d2dcfeb3012c40ad3c909d381406a6948d0ffe4a8c9080fccbbf2f` | 1 |
| `microsd-card-states-stack/removal-control-reset.log` | `419981d237924aa424f1d6021f1000e5fedccc8f8aee18738d916f586e9ff52a` | `8570abca828f728a7f663db713f488f6fb21ae13ce933f875262221de61e0f9f` | 1 |
| `microsd-card-states-stack/removal-flash.log` | `8ceb42bfa99109361bc2253aa31a33af1115d725faee8181dbcc81f84413fd69` | `e461c34e1436d189497f64b7f37bdaed2eec2f0952dad36a0c9331a3e2abe2e3` | 1 |
| `microsd-card-states-stack/removal-preflight.log` | `be28e73fbecf29317fbee64f9bdb3d3a7eb26ddad0c78122b5cd4bf1851d222d` | `698f1a5fb71b534c3100fc009a088f9e99badae2584192fc97f6bdd1a6df1fdf` | 1 |
| `microsd-card-states-stack/removal-restore.log` | `d4c33d3c9dc64207dd1020777ee03203764424db63c02d441e7d607fc8bcd41c` | `a79df7e88f9ae5cc9d977cf4496f132a79573af642345c122ae26a752e176a95` | 1 |
| `microsd-card-states-stack/stack-flash.log` | `69253da36ecf3611f732b574aaec1d71780f0e55160be66f200314f1789c2c9c` | `81d1dfac17fd1126ffd1b229a8d9fb725298cabc96c3b68486b65605285a11b2` | 1 |
| `microsd-card-states-stack/stack-preflight.log` | `dd96811cbd55f5e93b2605c327ec38c66a48f9e1099017c84b84a04b2946414c` | `16ce5b009522d1afc06e3f165b4763cd24f5761a1579548c38df2978b511f510` | 1 |
| `microsd-card-states-stack/stack-restore.log` | `6d5a2b849b2fb98e14d695e99fed73e47062331fb77bce54d744c8d81072de93` | `8bc029b99de80729c2ddfbf202c11e1d0362881097deb4d1d021cbefb01b2919` | 1 |
| `microsd-physical/README.md` | `811a8e76ae22201b02fe0dd99b24fda0530e321c296414d72d4eb1ac1d5cd403` | `302e7da37b34260301b02254e9215367773752179c21054537d4fb172359ba35` | 1 |
| `microsd-physical/preflight-jlink.log` | `6b8b31e427145058a9a5fcabd254b59e4507ced7189fba96689b92e2338d8166` | `27416e6238d7639520550469665929b22d60f24d976c7b238ecbc70e4ffee249` | 1 |
| `microsd-physical/run1-flash-jlink.log` | `32c9d13d79c6264f8125f96dee7493d7f2b44c5c6dff970060ed27bf8ea74a3c` | `25920f806e251ec019c6e6e4057718400f6cae0e3908b162b3df7b7d0372fa57` | 1 |
| `microsd-physical/run1-reset-jlink.log` | `274f04ca2de7dc9d813a9604b1c99d63803bc53ee5cb4fb27192803f8ddcc995` | `2a4974cebc1b86da8fa1e4cb19eca9b9c887b331de15ea964a01bff8ab3d2318` | 1 |
| `microsd-physical/run2-flash-jlink.log` | `55323b03e1bd908ce1c65df734770f2b3ea5e3c1c2700e573d4348234a484929` | `8bac215d539ef53d713da1bb3f127add8e44b13b522b1c932ddbd1b999df9cc8` | 1 |
| `microsd-physical/run2-reset-a-jlink.log` | `33c3c11478abc9e688b959dc65715dd447014abdfab81b9cb00b90d9743e909e` | `00dd0711cd1b99679f6a3ea0242d56e7547c058d8ee27db2e3c2075fdc9fc55e` | 1 |
| `microsd-physical/run2-reset-b-jlink.log` | `c3e96312996a10660ccae6572dab259e058140a4fb203dfdf544ee785d928d46` | `402aa216d6591a469d01e1ba13a65b85999765d987d9b40aadbb8ae43660ad5c` | 1 |
| `microsd-power-cut/flash-interrupt-image.log` | `059249d28b4a513f25a560fd55deebf2812dbfcf204269c41f85dcda002d02d1` | `db5daf1fc871b431ca5ce2c3d06f6fe77f717a575a1ca4f030c2a960a199b660` | 1 |
| `microsd-replace-cut/flash-replace-image.log` | `0775357e439cbde5ad494223d6654cb742989618ca07321e0e953e71d12e87a2` | `9986590d2dfb693ae1e7de5248d89a99ad9ed1de1c695fc14814f9e72503f5c8` | 1 |
| `networking-physical-integration/approval-red.log` | `c25dc5b2e59dae6c3b4668e14c55eead67e8a3b3dee14d447baf57d3743ca6e8` | `89fd62dc56368212069521f94496ef447f1006f307df9f9b22ac97a2f251f184` | 1 |
| `networking-physical-stage1-run2/01-second-run/boot-1/preflight-current-image.jlink` | `f5b0c6f0050a2a23cbdbee4936eb81ec9c65904687c824ea838190c8e67a90af` | `58f7d15913f3b086a41752be562add7f136920fc6079d9dc8f80db56f284ab9b` | 1 |
| `networking-physical-stage1-run2/01-second-run/boot-1/preflight-current-image.log` | `921ef03d196da9038c72dd13c844c98dd064ee9733a7f602e0b3829535839369` | `f187dbe16e87200f2048279fe64b1cb8d174db6039258393adb667c3b552f1a4` | 2 |
| `networking-physical-stage1-run2/01-second-run/boot-1/preflight-identity.jlink` | `84014764b5474d3fb2f05d2ce3732876c39022af22fc31caf03099108a539d61` | `2da2d7d29d73e985aff77641d11c061e80d599199476f6b26f64981987cb09e1` | 1 |
| `networking-physical-stage1-run2/01-second-run/boot-1/preflight-identity.log` | `756741ea4a3dcc6be3829c3887773686ef64cf87aeb10ed73d392e30c5f63260` | `4644ff2f2108b40bc2502758ca8bcd3f16828523542dbdfc6f1290230a964b97` | 2 |
| `networking-physical-stage1-run2/01-second-run/boot-1/qualification-reset.jlink` | `de9b6c1ab34f54acce30fc57118814a57dce0c3d332e2689cd2924b15673cbc5` | `fc8c4f89424460cb009b08e95e4c8b304bd3584882ad45d6c08a95ca42ef42fa` | 1 |
| `networking-physical-stage1-run2/01-second-run/boot-1/qualification-reset.log` | `d17fb8a4b1baf5d590f8bddb4bfa221c5f00d4964a2acd1397619cd8da0ec7dd` | `b66ff25c106d4213b534e154bada3390ed05d28d3a7f5b44b87759d5853797b5` | 2 |
| `networking-physical-stage1-run2/01-second-run/identify/01-identity-only.jlink` | `84014764b5474d3fb2f05d2ce3732876c39022af22fc31caf03099108a539d61` | `2da2d7d29d73e985aff77641d11c061e80d599199476f6b26f64981987cb09e1` | 1 |
| `networking-physical-stage1-run2/01-second-run/identify/01-identity-only.log` | `ce3d12dda231e0cc047243ab64f4a20b42910c3a67cff15f964e66a17af26bb3` | `2bde83894697261be942e1e601ad7d0892f27603fd7b38b97d74e16532e87885` | 2 |
| `networking-physical-stage1-run2/01-second-run/identify/02-candidate-integrated-normal.jlink` | `d3fada9d70539367c96f2c16c5523090a0fafde4995efc582b79c31767d3809f` | `7af55d0d3c6e2247efc322807c53513b2b9207274f1568615428506eb76a0898` | 1 |
| `networking-physical-stage1-run2/01-second-run/identify/02-candidate-integrated-normal.log` | `43f993c60d6e0ddeccf75e94444138fcea454d36270d00f72096d154b6df6bdf` | `4a85ae608bbe6db9d7a4daa57e7ca003c6e6edba62c4b4c332b539627f42c4c5` | 2 |
| `networking-physical-stage1-run2/01-second-run/program/01-identity-only.jlink` | `84014764b5474d3fb2f05d2ce3732876c39022af22fc31caf03099108a539d61` | `2da2d7d29d73e985aff77641d11c061e80d599199476f6b26f64981987cb09e1` | 1 |
| `networking-physical-stage1-run2/01-second-run/program/01-identity-only.log` | `42dbee066e565edc08e30fd44de66d36c2dd67f01e31f1335c0a5fefc67f8889` | `760cf3b01c13e04c3725d2462f76afa247f1c71be7f4b66b0ef4674508ce88f5` | 2 |
| `networking-physical-stage1-run2/01-second-run/program/02-entry-image.jlink` | `d3fada9d70539367c96f2c16c5523090a0fafde4995efc582b79c31767d3809f` | `7af55d0d3c6e2247efc322807c53513b2b9207274f1568615428506eb76a0898` | 1 |
| `networking-physical-stage1-run2/01-second-run/program/02-entry-image.log` | `eb2632909b7a78c81e42a8ee91af202f3355b67c173be8e8b17fda3580d87217` | `da4eeab962ca5effcb36815fe063d281ae7793321395cb74b5e70e89e2396395` | 2 |
| `networking-physical-stage1-run2/01-second-run/program/03-program-m5.jlink` | `369216b53727a57a65d08d005baf86a62bd8dfe499666fbf1a27a404cdd545b7` | `25f6dcde8a20312f0162f24d7f898306277b5c290171c460a793b9e038473451` | 1 |
| `networking-physical-stage1-run2/01-second-run/program/03-program-m5.log` | `40fb77a04eab57139c3c7bfe43cfc7ff0bfde9ba74e3cadea62a496fc24e65d6` | `203c7aa0816851ff1c6ab7a42a7112ead6b2a3a9d6a4571f6443ea7fe7939387` | 2 |
| `networking-physical-stage1-run2/01-second-run/restore/01-identity-only.jlink` | `84014764b5474d3fb2f05d2ce3732876c39022af22fc31caf03099108a539d61` | `2da2d7d29d73e985aff77641d11c061e80d599199476f6b26f64981987cb09e1` | 1 |
| `networking-physical-stage1-run2/01-second-run/restore/01-identity-only.log` | `684680f9b0c1a63a15ce5d0e2d56467df40587a0beb84e55054aecdc932d2f04` | `99d8d91160ab1040965302b02b68842af16234486eb8610cab0dcdcd9082001a` | 2 |
| `networking-physical-stage1-run2/01-second-run/restore/02-load-normal.jlink` | `609544efa65282163e999e0b512498488c728e5531481be3cfd56c916931465c` | `01ae74874fc0a03720772f19ef9429fae59c38e4033f328f1eac9ed9c1262bdd` | 1 |
| `networking-physical-stage1-run2/01-second-run/restore/02-load-normal.log` | `9d49d12ce1d1ea78919e5b8d875ee4f216620fc3abe4876cc5fea5b3227f437d` | `751269b5ee81eb9e2c78a40bd601cb59a8ddb0adeace028cdb3723453f8c044b` | 2 |
| `networking-physical-stage1-run2/01-second-run/restore/03-verify-normal.jlink` | `23f10896d11d218acb9b95c729e0bde8a8c1e4881bc853010750390c7267ff34` | `c4b5c1af5d495aa5f3f5a8193792db2b9098ffad12b3d3d9bc3a5a3839868ab4` | 1 |
| `networking-physical-stage1-run2/01-second-run/restore/03-verify-normal.log` | `533939a95badfd13850999cb2190efbb82c65259ccee9db5f65a01a91c544843` | `a0dbbca4df8882561043f25f4fae546cf7dcfbf15e961b16b73c782d5455f31e` | 2 |
| `networking-physical-stage1-run2/01-second-run/restore/04-start-normal.jlink` | `de9b6c1ab34f54acce30fc57118814a57dce0c3d332e2689cd2924b15673cbc5` | `fc8c4f89424460cb009b08e95e4c8b304bd3584882ad45d6c08a95ca42ef42fa` | 1 |
| `networking-physical-stage1-run2/01-second-run/restore/04-start-normal.log` | `7362759d3a95cb9216498a03a23e411e3e6b92e974fa75ef51bada6906595735` | `46cbecd21c5ef6a6743dbda753078cea99cbf4196490754aa41f315e74eaa45d` | 2 |
| `networking-physical-stage1-run2/README.md` | `81e62e98061502ccb6a69a92e1fdb0f60ecfb6877957aa04d16a3d9f0d7d5f96` | `c72a5affdd758caa5aad5ab75a91e154dc2689c116ddf09ec89b89349a8a3b29` | 1 |
| `networking-physical-stage1-run2/SHA256SUMS.tsv` | `34421214e9e546bacc86a8fa9ea540254de5a342c5ed299c4bc2e7680787b412` | `12b2ea9eea6108b4f5e853740935f401cbe490fe6caf1a770bcb1b5b8a2a6afb` | 1 |
| `networking-physical-stage1-run2/inputs/approval-m5-stage1-b44b66a.json` | `1093a742a4971e96f62e5d2e6840e9a0c05c6c2e88f808b886f1ca362982725c` | `d0be39109f93755632d550a2582aafebcb4309a569836509be7e5aa08923866d` | 1 |
| `networking-physical-stage1-run2/inputs/plan-m5-stage1-b44b66a.json` | `025b7527c0f46632ed86678501ab5e2992eb74b7ec567903b46730df41ee19d2` | `31189fc7ceec87499277a108cd002124a29be99e72c8aba48fe7bb6b70514611` | 2 |
| `networking-physical-stage1-run3/01-third-run/boot-1/preflight-current-image.jlink` | `c223746f920df6de2eec2a2a41f23dd52ebab749eb597d94364efb04ce84a240` | `8b2ee9e289106b3a188b3045d4607e3d36e3b37dc3413f2bd4cfb3f8b3916ec4` | 1 |
| `networking-physical-stage1-run3/01-third-run/boot-1/preflight-current-image.log` | `4662f3bbeae13ce218a6b4ffb8548e3d44b7c5b0251d3060f84a46eb6ab6a9d6` | `36a0b6b24a19e9bda90e88db54de00c2d36b5fa325779b1596c336c86d24756f` | 2 |
| `networking-physical-stage1-run3/01-third-run/boot-1/preflight-identity.jlink` | `84014764b5474d3fb2f05d2ce3732876c39022af22fc31caf03099108a539d61` | `2da2d7d29d73e985aff77641d11c061e80d599199476f6b26f64981987cb09e1` | 1 |
| `networking-physical-stage1-run3/01-third-run/boot-1/preflight-identity.log` | `34eab01d8b2c36af83657b550a0424c3c9db5000db7032b114266116d14e9968` | `1134b141ff36768f3284ecb9af0137bea1ec5f44602c5db1f735eec0f88049f0` | 2 |
| `networking-physical-stage1-run3/01-third-run/boot-1/qualification-reset.jlink` | `de9b6c1ab34f54acce30fc57118814a57dce0c3d332e2689cd2924b15673cbc5` | `fc8c4f89424460cb009b08e95e4c8b304bd3584882ad45d6c08a95ca42ef42fa` | 1 |
| `networking-physical-stage1-run3/01-third-run/boot-1/qualification-reset.log` | `680c9b8b6364ede4a3c29c93a151ade38620e882bd6e352dd7bdd34cf41fa013` | `5e226990805048cc265360fe0b5c122a5ae4047ef5a5f754e42b13bcac94e7d0` | 2 |
| `networking-physical-stage1-run3/01-third-run/identify/01-identity-only.jlink` | `84014764b5474d3fb2f05d2ce3732876c39022af22fc31caf03099108a539d61` | `2da2d7d29d73e985aff77641d11c061e80d599199476f6b26f64981987cb09e1` | 1 |
| `networking-physical-stage1-run3/01-third-run/identify/01-identity-only.log` | `f1bc385b030cd3a75186eb25d5a13b1a215120ce086efe81be03ae7b8e6d5556` | `2a7cda4397d15b12c16a2e4c1470ab97ec598a90d1809b5b897705f701ac8adf` | 2 |
| `networking-physical-stage1-run3/01-third-run/identify/02-candidate-integrated-normal.jlink` | `d3fada9d70539367c96f2c16c5523090a0fafde4995efc582b79c31767d3809f` | `7af55d0d3c6e2247efc322807c53513b2b9207274f1568615428506eb76a0898` | 1 |
| `networking-physical-stage1-run3/01-third-run/identify/02-candidate-integrated-normal.log` | `e2e012e7959f8dbf9538bb64820ca919cec2a06291ad4b98440d20802ca2b38f` | `5df0439b2278942e3140a9d236f8a45fc088ca17644e78324e05119758691fcc` | 2 |
| `networking-physical-stage1-run3/01-third-run/program/01-identity-only.jlink` | `84014764b5474d3fb2f05d2ce3732876c39022af22fc31caf03099108a539d61` | `2da2d7d29d73e985aff77641d11c061e80d599199476f6b26f64981987cb09e1` | 1 |
| `networking-physical-stage1-run3/01-third-run/program/01-identity-only.log` | `928bd5eb2958bee067589705ce02448daa130f5a1fb30aa7d8094a31101ffe71` | `0d85fef7b330c0b235dc77c1531eea0313edcd81d634692b23d8ff49ad99c798` | 2 |
| `networking-physical-stage1-run3/01-third-run/program/02-entry-image.jlink` | `d3fada9d70539367c96f2c16c5523090a0fafde4995efc582b79c31767d3809f` | `7af55d0d3c6e2247efc322807c53513b2b9207274f1568615428506eb76a0898` | 1 |
| `networking-physical-stage1-run3/01-third-run/program/02-entry-image.log` | `437ecae7f5b8efe9b265517bbfcefa7cf74c3489d0f212c2a7f73ffcde0bc7b9` | `4e6144867e9df88c40013952d170cf28973bf487e4538bd7aed434f2e09781e0` | 2 |
| `networking-physical-stage1-run3/01-third-run/program/03-program-m5.jlink` | `ea00dfc64dee7d3b075ba14bdc032fb156a2c6d7e38b662192ea4ff7abcf8cbf` | `1e244a03318c0264eba721490f9fc64b35cd7bc96079f235c479eca2715863cb` | 1 |
| `networking-physical-stage1-run3/01-third-run/restore/01-identity-only.jlink` | `84014764b5474d3fb2f05d2ce3732876c39022af22fc31caf03099108a539d61` | `2da2d7d29d73e985aff77641d11c061e80d599199476f6b26f64981987cb09e1` | 1 |
| `networking-physical-stage1-run3/01-third-run/restore/01-identity-only.log` | `3d7022490de3495e77165f5c4ad904865a0a01e3c0e8c3e82a4126f9f7250724` | `72dfac7fd2686df9952e7e04b7d8caceaaf95de9dafe43e235952e599816c095` | 2 |
| `networking-physical-stage1-run3/01-third-run/restore/02-load-normal.jlink` | `609544efa65282163e999e0b512498488c728e5531481be3cfd56c916931465c` | `01ae74874fc0a03720772f19ef9429fae59c38e4033f328f1eac9ed9c1262bdd` | 1 |
| `networking-physical-stage1-run3/01-third-run/restore/03-verify-normal.jlink` | `23f10896d11d218acb9b95c729e0bde8a8c1e4881bc853010750390c7267ff34` | `c4b5c1af5d495aa5f3f5a8193792db2b9098ffad12b3d3d9bc3a5a3839868ab4` | 1 |
| `networking-physical-stage1-run3/01-third-run/restore/04-start-normal.jlink` | `de9b6c1ab34f54acce30fc57118814a57dce0c3d332e2689cd2924b15673cbc5` | `fc8c4f89424460cb009b08e95e4c8b304bd3584882ad45d6c08a95ca42ef42fa` | 1 |
| `networking-physical-stage1-run3/README.md` | `f7f3f047a4bd6e62cd07b904d7e8634df8c8f5eaef1044f423c03083ff06a502` | `658edef5cc55a81e395522c802d365726982f0d9f66bdaacac87f1655958fab8` | 1 |
| `networking-physical-stage1-run3/SHA256SUMS.tsv` | `b373f5d41d6eaa6311edc10300ea6969132384c75f0b62e8e1311fc12bbdbf7b` | `5e129f0becfa3b36e749ac7b3bb866ba0ca75e9e45b4b8eadc69a14284e51768` | 1 |
| `networking-physical-stage1-run3/inputs/approval-m5-stage1-94a4a7d.json` | `f315aabf05082b715ab6ecc6188e84f278d8c8dd971c372606dd545198b73a1e` | `0ebaa8c246ba683932cc0b2a83612950206a161c96839ef1229d3bb08e1a7153` | 1 |
| `networking-physical-stage1-run3/inputs/plan-m5-stage1-94a4a7d.json` | `39cda83484621544686a8c423d0037c8aa6f1dc04391fdd580217089f83742b7` | `8d8cbbef3a92c5b128cd0ff0688a83e327924d804faeffafad334d3a37f3aadf` | 2 |
| `networking-physical-stage1/02-identify-found-unknown-firmware/identify/01-identity-only.jlink` | `84014764b5474d3fb2f05d2ce3732876c39022af22fc31caf03099108a539d61` | `2da2d7d29d73e985aff77641d11c061e80d599199476f6b26f64981987cb09e1` | 1 |
| `networking-physical-stage1/02-identify-found-unknown-firmware/identify/01-identity-only.log` | `5bec9ecd9f943e8ecd8acd0c0748db21267ff4722fd0c7d7ef615f480e479f5a` | `1f3054218f2143f9f23a286840372915cf8a05976c3d8dd57d7b1ab12e03ecef` | 2 |
| `networking-physical-stage1/02-identify-found-unknown-firmware/identify/02-candidate-integrated-normal.jlink` | `d3fada9d70539367c96f2c16c5523090a0fafde4995efc582b79c31767d3809f` | `7af55d0d3c6e2247efc322807c53513b2b9207274f1568615428506eb76a0898` | 1 |
| `networking-physical-stage1/02-identify-found-unknown-firmware/identify/02-candidate-integrated-normal.log` | `5606e0b4e6e9fba3bee979191a086cc6d0a127c3b1a071c0e7ea975df6663d27` | `0b0acc2afe84e8d58da077fa323e750dbbed88c916461efb33ed058988ff821d` | 2 |
| `networking-physical-stage1/03-restore-stopped-diagnostic/restore/01-identity-only.jlink` | `84014764b5474d3fb2f05d2ce3732876c39022af22fc31caf03099108a539d61` | `2da2d7d29d73e985aff77641d11c061e80d599199476f6b26f64981987cb09e1` | 1 |
| `networking-physical-stage1/03-restore-stopped-diagnostic/restore/01-identity-only.log` | `b03dd8662ace33c18e9926c6555e8e041619b11c0617a46c971b066e86b1e1a1` | `f945a0e8903210640d0ca0f7d957e2da8de6e9cbd7a95e296d2551dfb263641c` | 2 |
| `networking-physical-stage1/03-restore-stopped-diagnostic/restore/02-load-normal.jlink` | `609544efa65282163e999e0b512498488c728e5531481be3cfd56c916931465c` | `01ae74874fc0a03720772f19ef9429fae59c38e4033f328f1eac9ed9c1262bdd` | 1 |
| `networking-physical-stage1/03-restore-stopped-diagnostic/restore/02-load-normal.log` | `d02d4880ca4ebf057ea8976cb756bd88185bd9f58f1d79645eeb46ba5c3fa635` | `1c979526eb25306b0021e8becc0f31b01a2ea25b50ca7e8d6e6995ee797073bc` | 2 |
| `networking-physical-stage1/04-identify-matched/identify/01-identity-only.jlink` | `84014764b5474d3fb2f05d2ce3732876c39022af22fc31caf03099108a539d61` | `2da2d7d29d73e985aff77641d11c061e80d599199476f6b26f64981987cb09e1` | 1 |
| `networking-physical-stage1/04-identify-matched/identify/01-identity-only.log` | `63cd03d7dd3b3cea683efa2ada9f635c56135c1027bb13ce196658456e389697` | `74fd586ce6e37cec629dd4e7b336f5428f518d24c52068f8b79e272ea7c6b2b7` | 2 |
| `networking-physical-stage1/04-identify-matched/identify/02-candidate-integrated-normal.jlink` | `d3fada9d70539367c96f2c16c5523090a0fafde4995efc582b79c31767d3809f` | `7af55d0d3c6e2247efc322807c53513b2b9207274f1568615428506eb76a0898` | 1 |
| `networking-physical-stage1/04-identify-matched/identify/02-candidate-integrated-normal.log` | `4b40977bef83b56e2d98f038d80b0054ddab499e942a395a4b070f20bb370c98` | `79956d88491d8cb8dd725f10e0b7aa70cb64a8a5d82a7a43723deaac19d18e4a` | 2 |
| `networking-physical-stage1/05-restore-fixed-driver/restore/01-identity-only.jlink` | `84014764b5474d3fb2f05d2ce3732876c39022af22fc31caf03099108a539d61` | `2da2d7d29d73e985aff77641d11c061e80d599199476f6b26f64981987cb09e1` | 1 |
| `networking-physical-stage1/05-restore-fixed-driver/restore/01-identity-only.log` | `468a4ffec32f11c4c6ca463a5b7c444f0dd42daf41edae1ae6efe4cea6af6ee3` | `99d71a498fc0b6f643eb6fcf1323d7185fb883da397b279240d658be56117eb0` | 2 |
| `networking-physical-stage1/05-restore-fixed-driver/restore/02-load-normal.jlink` | `609544efa65282163e999e0b512498488c728e5531481be3cfd56c916931465c` | `01ae74874fc0a03720772f19ef9429fae59c38e4033f328f1eac9ed9c1262bdd` | 1 |
| `networking-physical-stage1/05-restore-fixed-driver/restore/03-verify-normal.jlink` | `23f10896d11d218acb9b95c729e0bde8a8c1e4881bc853010750390c7267ff34` | `c4b5c1af5d495aa5f3f5a8193792db2b9098ffad12b3d3d9bc3a5a3839868ab4` | 1 |
| `networking-physical-stage1/05-restore-fixed-driver/restore/03-verify-normal.log` | `819202c7a8b833dc471f2fca071b15522cf34792c1d4bb3ac6507b8dde018498` | `0450740683b4af1eea63a4132da31601105bcef070ccc6c64dff244e0b181723` | 2 |
| `networking-physical-stage1/05-restore-fixed-driver/restore/04-start-normal.jlink` | `de9b6c1ab34f54acce30fc57118814a57dce0c3d332e2689cd2924b15673cbc5` | `fc8c4f89424460cb009b08e95e4c8b304bd3584882ad45d6c08a95ca42ef42fa` | 1 |
| `networking-physical-stage1/05-restore-fixed-driver/restore/04-start-normal.log` | `c443bb993ed5736881f5a992be9cd68d33b9e241e192ac475203808b5129d1b3` | `05e80caeaac7e4b2d33008c17e34c021f34b1650b32154137c58516217b82661` | 2 |
| `networking-physical-stage1/06-main-run-program-capture-restore/boot-1/preflight-current-image.jlink` | `11a9494bbd5e50aa0812165e499d7f8995b8315a9e62d9e033aac08bfa4d3306` | `f449d6593799dd22a46380d205ceb39375ac52a6648690a4d06b6c9d150431b3` | 1 |
| `networking-physical-stage1/06-main-run-program-capture-restore/boot-1/preflight-current-image.log` | `b6e8c0fe9e34345efd47db9e2d69e563e812a23d54fbbd54bd6c4ad2112cb011` | `90db32b688a21cab63845c50554976321ada49bbf7d887f320734e16838edcbc` | 2 |
| `networking-physical-stage1/06-main-run-program-capture-restore/boot-1/preflight-identity.jlink` | `84014764b5474d3fb2f05d2ce3732876c39022af22fc31caf03099108a539d61` | `2da2d7d29d73e985aff77641d11c061e80d599199476f6b26f64981987cb09e1` | 1 |
| `networking-physical-stage1/06-main-run-program-capture-restore/boot-1/preflight-identity.log` | `4482af3c110d9b60416d21a2059a8f3831f42079f1a2255f81e1916bf063a02a` | `999add51636a24ce2d557e59c0e1d2e10c4f969fe3a87c5894b199179eb08736` | 2 |
| `networking-physical-stage1/06-main-run-program-capture-restore/boot-1/qualification-reset.jlink` | `de9b6c1ab34f54acce30fc57118814a57dce0c3d332e2689cd2924b15673cbc5` | `fc8c4f89424460cb009b08e95e4c8b304bd3584882ad45d6c08a95ca42ef42fa` | 1 |
| `networking-physical-stage1/06-main-run-program-capture-restore/boot-1/qualification-reset.log` | `689c665195964b7e068f41f8614a1aefe071d6f91da7fce1b470aff1506414c9` | `e1b3ead6cf28cf43139db90325dd6ec08246153d1fb20d3ab91c2687a99e0a7c` | 2 |
| `networking-physical-stage1/06-main-run-program-capture-restore/identify/01-identity-only.jlink` | `84014764b5474d3fb2f05d2ce3732876c39022af22fc31caf03099108a539d61` | `2da2d7d29d73e985aff77641d11c061e80d599199476f6b26f64981987cb09e1` | 1 |
| `networking-physical-stage1/06-main-run-program-capture-restore/identify/01-identity-only.log` | `995fca8d5566eee47cf94fe042529d5bd3dffce04ac60aa3c9830a236887fee9` | `eeab29e0e220cd771fad4473da7ff66c294e89cfb5c040f307c4f0beb2736f6c` | 2 |
| `networking-physical-stage1/06-main-run-program-capture-restore/identify/02-candidate-integrated-normal.jlink` | `d3fada9d70539367c96f2c16c5523090a0fafde4995efc582b79c31767d3809f` | `7af55d0d3c6e2247efc322807c53513b2b9207274f1568615428506eb76a0898` | 1 |
| `networking-physical-stage1/06-main-run-program-capture-restore/identify/02-candidate-integrated-normal.log` | `7523bd248049d94f592e3c321aae3e9e70bb0f390fe57663f04483fe1159f7a2` | `510b957cc26214a7f2ee4210d6a1cefab434f844f9eafcd83a6f45dbd4c4b26f` | 2 |
| `networking-physical-stage1/06-main-run-program-capture-restore/program/01-identity-only.jlink` | `84014764b5474d3fb2f05d2ce3732876c39022af22fc31caf03099108a539d61` | `2da2d7d29d73e985aff77641d11c061e80d599199476f6b26f64981987cb09e1` | 1 |
| `networking-physical-stage1/06-main-run-program-capture-restore/program/01-identity-only.log` | `74e15ad3d085d045687a61132d220ef155333beb4b94c2507cd82d8462b57431` | `6104752e9cce3e0cb855df369869a5d760bdb16255dce54ddc716b9327a84850` | 2 |
| `networking-physical-stage1/06-main-run-program-capture-restore/program/02-entry-image.jlink` | `d3fada9d70539367c96f2c16c5523090a0fafde4995efc582b79c31767d3809f` | `7af55d0d3c6e2247efc322807c53513b2b9207274f1568615428506eb76a0898` | 1 |
| `networking-physical-stage1/06-main-run-program-capture-restore/program/02-entry-image.log` | `adb3933a4bc31a1761a1ca18ac47de76803ef30710f805ecd1778cd23b343440` | `a81f66dde14bebbdf8f4b207cd11eb12efe9c2153992e53afd158c4f2a484b95` | 2 |
| `networking-physical-stage1/06-main-run-program-capture-restore/program/03-program-m5.jlink` | `5f65c517de27520d1b4777ab09d5acd602926b2eb2211b6a8ba26eef4fe72133` | `74a80cb64a8864531754f5d0ee26b16ee164ab6f3c2d0ac7aa84e68a0494b093` | 1 |
| `networking-physical-stage1/06-main-run-program-capture-restore/program/03-program-m5.log` | `5a3bce51a7a1f4199ea089122599a52e4f3d5aca10ef1fe5aefef2dd90f9d35a` | `20f14d40146067803e410a8bba5f000fc53372db65d5a393b4f45fc71acbe16e` | 2 |
| `networking-physical-stage1/06-main-run-program-capture-restore/restore/01-identity-only.jlink` | `84014764b5474d3fb2f05d2ce3732876c39022af22fc31caf03099108a539d61` | `2da2d7d29d73e985aff77641d11c061e80d599199476f6b26f64981987cb09e1` | 1 |
| `networking-physical-stage1/06-main-run-program-capture-restore/restore/01-identity-only.log` | `c958e1d2bdbb96e5d31ff78754b65cdf06b96812eac7576b23e73e5f3e9cffdb` | `bb21c9f40d01125736d3a5816af592269e240bd0759a8479451ecfaebfc4e2af` | 2 |
| `networking-physical-stage1/06-main-run-program-capture-restore/restore/02-load-normal.jlink` | `609544efa65282163e999e0b512498488c728e5531481be3cfd56c916931465c` | `01ae74874fc0a03720772f19ef9429fae59c38e4033f328f1eac9ed9c1262bdd` | 1 |
| `networking-physical-stage1/06-main-run-program-capture-restore/restore/02-load-normal.log` | `9b58aa0524df801114894f601bdda890ea943018a9ad053a1e74f923978518b3` | `a9cc9d3e8db235eefd0c5bb0d4a729dcea8b51df66e5c3c1ef9d224871ac48f1` | 2 |
| `networking-physical-stage1/06-main-run-program-capture-restore/restore/03-verify-normal.jlink` | `23f10896d11d218acb9b95c729e0bde8a8c1e4881bc853010750390c7267ff34` | `c4b5c1af5d495aa5f3f5a8193792db2b9098ffad12b3d3d9bc3a5a3839868ab4` | 1 |
| `networking-physical-stage1/06-main-run-program-capture-restore/restore/03-verify-normal.log` | `c031e27ec6133c0b8eb7b234cf1a16f498587ef905240773a24b58b77e72b5d9` | `baf53654acee7175d0da2b75e5b10446f48d9e710055dd5e391909a866de4676` | 2 |
| `networking-physical-stage1/06-main-run-program-capture-restore/restore/04-start-normal.jlink` | `de9b6c1ab34f54acce30fc57118814a57dce0c3d332e2689cd2924b15673cbc5` | `fc8c4f89424460cb009b08e95e4c8b304bd3584882ad45d6c08a95ca42ef42fa` | 1 |
| `networking-physical-stage1/06-main-run-program-capture-restore/restore/04-start-normal.log` | `dd39970c91d28d67513d902b63fb6a4d628d4999c7017976f348b2b5408f4f16` | `6d070103f095ec64b91ba0c8cd88de0bc8aae3bd93d47d1814dc8d3c0d8093fc` | 2 |
| `networking-physical-stage1/README.md` | `a2c61398fdc133dfc28639e2403c6a52bde2fb7f31a057f4522e3757f85da886` | `412ca3fd919c0c899a5c761950d6ef53df06864f7323bab5ddb591f94e3d2284` | 2 |
| `networking-physical-stage1/SHA256SUMS.tsv` | `c4bb812942ec83f2667e4717fe3e4f81a01f139fae89f9ff080cabf3b918e64b` | `caa365d4f0299f253c6df4dfe017194c45fc074dc5915ed8098b25fce5b4b40c` | 6 |
| `networking-physical-stage1/inputs/approval-m5-stage1-3ef758d.json` | `52425b6d95cd9d8a59882c8952449142939778247ca732f3fe0e88631d295808` | `83ce5d1be955e3c4ac6007482a3853bdefe9c2a2892ac6cc14dfe2116e653d47` | 1 |
| `networking-physical-stage1/inputs/plan-m5-stage1-3ef758d.json` | `bfdd1fb6ca66311bf2ff5670097f626b249e8ef68a61066b2498eec0f2a6cbe2` | `3b16f75c0181ac4a5b98721e54c4f0c82c86de08342c4d85c757b35322b8e292` | 2 |
| `networking-physical-stage1/inputs/plans/stage1-phase-b-plan-r4.md` | `4940f271ba23faa49700f61d26177d4e2de92f6477974323cc7151acff7fdd4e` | `54a37486bee3e1714b49a777d0b2898a2bd368b2201cfa1c2ec90b71bd16fab2` | 1 |
| `networking-physical-stage1/inputs/plans/stage1-phase-b-plan.md` | `0f7970b13f41feee5538ba76cb2d200c47b192ae0e7cbb08e0e0ca38ba72c82b` | `8617fa2497bb25de2a5cb77d122ae2951a42377c250a0aaf345e6b2a1d00d3bb` | 3 |
| `networking-physical/preflight-red.log` | `fee51e5571c2940575694f174c61cc80e5bf7a00382e32ad9159895092ec8b80` | `aecff082fabf1d4aaa79ae612ea04a201cd7b8645e2535ce1b7c868b295309f1` | 6 |
| `psa-crypto/rt1060-board-2026-11-07/README.md` | `f6d27e268331b1ff6299bf0cd5588ad892d13e46dc3d4f0c7959e1f5466907a1` | `d003a3031efed705e04db6937573e42857ea90e9e029bea64cd8e62c769bb98e` | 1 |
| `psa-crypto/rt1060-board-2026-11-07/run-1-events.log` | `f4f55386d3ca8cd87a796df9b1f1bbf6eaa301b9a36f4a9034b3f693ba34dfc3` | `a6be75ecc7e9822f3866f21ce9363b72034aa9dab84d17c1567bdb122f13e7c9` | 4 |
| `psa-crypto/rt1060-board-2026-11-07/run-1-result.json` | `c4894af55c2553efd9d5914ffaeb528ad35e5d00208e243a1dba6464984e79e6` | `c78b1319375be3c9a8b82d7f729f11e26d5c4e78386a2d37753d350abfee1c76` | 4 |
| `psa-crypto/rt1060-board-2026-11-07/run-2-events.log` | `e3674a1396d0475c1567cd46966b339464880ca82a6509fb02ac2504521f05b0` | `d662a512a12d1aa15288d7aec78823053b1c900726633c7293311dcc953b7e02` | 7 |
| `psa-crypto/rt1060-board-2026-11-07/run-2-result.json` | `9faee9cad2a8fed685c40968ae3006f996aeff7f2eacfdb6eaaa59c61a99f5dd` | `188e6871413bff2d96aff64a4c1873d20377e6e69b2026744537b6a791e21f7b` | 7 |
