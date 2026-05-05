# Changelog

## [1.11.1](https://github.com/cds-snc/gc-sign-in-migration/compare/v1.11.0...v1.11.1) (2026-05-05)


### Bug Fixes

* **GA:** added support to pass rp name and client id and also trigger completi… ([#285](https://github.com/cds-snc/gc-sign-in-migration/issues/285)) ([5422e47](https://github.com/cds-snc/gc-sign-in-migration/commit/5422e474ec275ca6309c0e7961a777205586ed3d))

## [1.11.0](https://github.com/cds-snc/gc-sign-in-migration/compare/v1.10.16...v1.11.0) (2026-04-30)


### Features

* Implement load test system in CI, disabled for now ([#283](https://github.com/cds-snc/gc-sign-in-migration/issues/283)) ([32db907](https://github.com/cds-snc/gc-sign-in-migration/commit/32db907aa9b373a64a88928f6ff3624059f17837))


### Bug Fixes

* **staging:** deploy ([#280](https://github.com/cds-snc/gc-sign-in-migration/issues/280)) ([636fe8d](https://github.com/cds-snc/gc-sign-in-migration/commit/636fe8de1b2537c936438967c6fc5feed4fd682d))

## [1.10.16](https://github.com/cds-snc/gc-sign-in-migration/compare/v1.10.15...v1.10.16) (2026-04-28)


### Bug Fixes

* **logs:** resolve issue with logs exceeding 1000 characters per entry ([#276](https://github.com/cds-snc/gc-sign-in-migration/issues/276)) ([d15b2ef](https://github.com/cds-snc/gc-sign-in-migration/commit/d15b2ef6e55ab5ac1f5eaca0e6b982309d14c078))

## [1.10.15](https://github.com/cds-snc/gc-sign-in-migration/compare/v1.10.14...v1.10.15) (2026-04-15)


### Bug Fixes

* **bug:** add missing info banner with english and french urls ([#267](https://github.com/cds-snc/gc-sign-in-migration/issues/267)) ([7889b7f](https://github.com/cds-snc/gc-sign-in-migration/commit/7889b7f13697b05290004bdbd52cf5a53f3fc8a4))
* **release:** deploy to prod ([#265](https://github.com/cds-snc/gc-sign-in-migration/issues/265)) ([4836dc4](https://github.com/cds-snc/gc-sign-in-migration/commit/4836dc4d17d6e9cc3239e68f004753daa567a1f2))

## [1.10.14](https://github.com/cds-snc/gc-sign-in-migration/compare/v1.10.13...v1.10.14) (2026-04-14)


### Bug Fixes

* **release:** release to test and staging ([#263](https://github.com/cds-snc/gc-sign-in-migration/issues/263)) ([d565b41](https://github.com/cds-snc/gc-sign-in-migration/commit/d565b41650763ecc44a1def885704acb97900a55))
* **release:** releasling latest to test and staging ([#259](https://github.com/cds-snc/gc-sign-in-migration/issues/259)) ([cbb53dc](https://github.com/cds-snc/gc-sign-in-migration/commit/cbb53dcd7e6f68deec6feb0938a3169133721ef6))

## [1.10.13](https://github.com/cds-snc/gc-sign-in-migration/compare/v1.10.12...v1.10.13) (2026-04-13)


### Bug Fixes

* **deps:** update dependency axios to &gt;=1.13.5 &lt;1.15.1 [security] ([#241](https://github.com/cds-snc/gc-sign-in-migration/issues/241)) ([c68a693](https://github.com/cds-snc/gc-sign-in-migration/commit/c68a693baf953d18af5f307a9716a04b030e7cde))
* **migration:** fail closed on SIC and Redis dependency errors ([#252](https://github.com/cds-snc/gc-sign-in-migration/issues/252)) ([7da1918](https://github.com/cds-snc/gc-sign-in-migration/commit/7da1918bc172ac3ea1b605a55deb5693c6d9cb3d))
* **saa:** implemented code to meet controls ([#254](https://github.com/cds-snc/gc-sign-in-migration/issues/254)) ([80d79e8](https://github.com/cds-snc/gc-sign-in-migration/commit/80d79e8fd80e4f9ded1a1cdc16b829af1d764166))

## [1.10.12](https://github.com/cds-snc/gc-sign-in-migration/compare/v1.10.11...v1.10.12) (2026-04-12)


### Bug Fixes

* **axios:** updated the versioning around axios ([#237](https://github.com/cds-snc/gc-sign-in-migration/issues/237)) ([2ec845f](https://github.com/cds-snc/gc-sign-in-migration/commit/2ec845fd51173e37c12ff46382bc3e87ec27c256))
* **lang:** added missing french translations ([#239](https://github.com/cds-snc/gc-sign-in-migration/issues/239)) ([e47de50](https://github.com/cds-snc/gc-sign-in-migration/commit/e47de501f53b531e1dee200df2752772f3c9d3dd))
* **logging:** added correlation ids and cleaned up logging a bit to c… ([#250](https://github.com/cds-snc/gc-sign-in-migration/issues/250)) ([a1dc8ed](https://github.com/cds-snc/gc-sign-in-migration/commit/a1dc8edd5cfca0567af50846a1acbbce2e76bd42))
* **staging:** deploy to staging ([#242](https://github.com/cds-snc/gc-sign-in-migration/issues/242)) ([ff84422](https://github.com/cds-snc/gc-sign-in-migration/commit/ff8442233e82ab0028afb255d79252fba45b49a2))


### Miscellaneous Chores

* **deps:** bump cryptography from 46.0.5 to 46.0.7 in /backend ([#238](https://github.com/cds-snc/gc-sign-in-migration/issues/238)) ([eb90156](https://github.com/cds-snc/gc-sign-in-migration/commit/eb901560d5853272b788164df5716ae1f60c1f18))
* **deps:** bump requests from 2.32.5 to 2.33.0 in /backend ([#224](https://github.com/cds-snc/gc-sign-in-migration/issues/224)) ([eb31928](https://github.com/cds-snc/gc-sign-in-migration/commit/eb31928a7342d1302cb9ea1369328dc625da7b84))
* **deps:** update all patch dependencies ([#217](https://github.com/cds-snc/gc-sign-in-migration/issues/217)) ([17feb54](https://github.com/cds-snc/gc-sign-in-migration/commit/17feb5429c1a4a5cf2904d95aad00477410ededc))
* **deps:** update all patch dependencies ([#253](https://github.com/cds-snc/gc-sign-in-migration/issues/253)) ([28d2109](https://github.com/cds-snc/gc-sign-in-migration/commit/28d2109abb7ad8f469f99f754d2111bc953f0b2b))
* **deps:** update dependency uvicorn to v0.43.0 ([#228](https://github.com/cds-snc/gc-sign-in-migration/issues/228)) ([7fd667b](https://github.com/cds-snc/gc-sign-in-migration/commit/7fd667b912dd2127db000b1d664703c64a4e957e))

## [1.10.11](https://github.com/cds-snc/gc-sign-in-migration/compare/v1.10.10...v1.10.11) (2026-03-26)


### Bug Fixes

* **logging:** removed and cleanup logging, was to much uncessarily been logged to a… ([#225](https://github.com/cds-snc/gc-sign-in-migration/issues/225)) ([adb6a4d](https://github.com/cds-snc/gc-sign-in-migration/commit/adb6a4d0a3a3f4ecee57beb51eb7d81ff92fcbc5))

## [1.10.10](https://github.com/cds-snc/gc-sign-in-migration/compare/v1.10.9...v1.10.10) (2026-03-24)


### Bug Fixes

* **extraParam:** support for extra parameters being sent bt RP to IBM… ([#212](https://github.com/cds-snc/gc-sign-in-migration/issues/212)) ([4f74c8b](https://github.com/cds-snc/gc-sign-in-migration/commit/4f74c8b9cb054f43ce71169c1725ba5db12b436d))
* **language:** Feature/new french t ranslations ([#222](https://github.com/cds-snc/gc-sign-in-migration/issues/222)) ([5238903](https://github.com/cds-snc/gc-sign-in-migration/commit/5238903c3f4cf539b4064885ea31945f2ae3e9d7))
* **staging:** deploy to staging ([#208](https://github.com/cds-snc/gc-sign-in-migration/issues/208)) ([db7c400](https://github.com/cds-snc/gc-sign-in-migration/commit/db7c4006585481afc5207e6d529509a732cc433c))

## [1.10.9](https://github.com/cds-snc/gc-sign-in-migration/compare/v1.10.8...v1.10.9) (2026-03-17)


### Miscellaneous Chores

* **deps:** update dependency pre-commit to v4.5.1 ([#203](https://github.com/cds-snc/gc-sign-in-migration/issues/203)) ([77c97a9](https://github.com/cds-snc/gc-sign-in-migration/commit/77c97a9029a75a176de77bafbbab2b5dd67112ea))
* **deps:** update dependency pyjwt to v2.12.0 [security] ([#202](https://github.com/cds-snc/gc-sign-in-migration/issues/202)) ([d5bcf31](https://github.com/cds-snc/gc-sign-in-migration/commit/d5bcf31ad3045310c5059dec8c3d734701f1afac))

## [1.10.8](https://github.com/cds-snc/gc-sign-in-migration/compare/v1.10.7...v1.10.8) (2026-03-17)


### Bug Fixes

* **forceRelease:** forceRelease ([#205](https://github.com/cds-snc/gc-sign-in-migration/issues/205)) ([c047360](https://github.com/cds-snc/gc-sign-in-migration/commit/c0473602c76125a5f84163958a083967b90a6107))

## [1.10.7](https://github.com/cds-snc/gc-sign-in-migration/compare/v1.10.6...v1.10.7) (2026-03-11)


### Bug Fixes

* added more support for gckey only flow ([#192](https://github.com/cds-snc/gc-sign-in-migration/issues/192)) ([d645d5d](https://github.com/cds-snc/gc-sign-in-migration/commit/d645d5dc7c12a1bd9671f3adf48ecb11aa8142d0))


### Miscellaneous Chores

* **deps:** update all patch dependencies ([#183](https://github.com/cds-snc/gc-sign-in-migration/issues/183)) ([255cff9](https://github.com/cds-snc/gc-sign-in-migration/commit/255cff9609c14539f64bea6209192610878fe5e0))
* **deps:** update dependency fastapi to v0.135.1 ([#185](https://github.com/cds-snc/gc-sign-in-migration/issues/185)) ([fe377fe](https://github.com/cds-snc/gc-sign-in-migration/commit/fe377fe1ae517e2a715327ea9b13394ae1a22581))


### Continuous Integration

* Update version to 1.10.6 in prod.json ([#179](https://github.com/cds-snc/gc-sign-in-migration/issues/179)) ([b59b828](https://github.com/cds-snc/gc-sign-in-migration/commit/b59b828d47c29e4a0692a0dad25bbad80545ba3b))

## [1.10.6](https://github.com/cds-snc/gc-sign-in-migration/compare/v1.10.5...v1.10.6) (2026-03-05)


### Bug Fixes

* Fix formatting issue in README.md ([#177](https://github.com/cds-snc/gc-sign-in-migration/issues/177)) ([20f0700](https://github.com/cds-snc/gc-sign-in-migration/commit/20f07000a2e76f028bcf6f15d41e53f9b4f2ba6a))

## [1.10.5](https://github.com/cds-snc/gc-sign-in-migration/compare/v1.10.4...v1.10.5) (2026-03-05)


### Continuous Integration

* updated staging version "1.10.4" ([#172](https://github.com/cds-snc/gc-sign-in-migration/issues/172)) ([5e03b5a](https://github.com/cds-snc/gc-sign-in-migration/commit/5e03b5a8e439136a5ba72624bfab2dd139ce706e))

## [1.10.4](https://github.com/cds-snc/gc-sign-in-migration/compare/v1.10.3...v1.10.4) (2026-03-05)


### Bug Fixes

* **forceRelease:** made a small change to force release ([f75d63d](https://github.com/cds-snc/gc-sign-in-migration/commit/f75d63d503b5cdf983516e252223d2d4bde30dbb))
* **forceRelease:** made a small change to force release ([#169](https://github.com/cds-snc/gc-sign-in-migration/issues/169)) ([f75d63d](https://github.com/cds-snc/gc-sign-in-migration/commit/f75d63d503b5cdf983516e252223d2d4bde30dbb))

## [1.10.3](https://github.com/cds-snc/gc-sign-in-migration/compare/v1.10.2...v1.10.3) (2026-03-02)


### Bug Fixes

* **language:** supports the language cookie from SIC and GCCF (and in… ([#160](https://github.com/cds-snc/gc-sign-in-migration/issues/160)) ([529fb4d](https://github.com/cds-snc/gc-sign-in-migration/commit/529fb4d191b117de156d4c7472b324d49e711383))

## [1.10.2](https://github.com/cds-snc/gc-sign-in-migration/compare/v1.10.1...v1.10.2) (2026-03-02)


### Bug Fixes

* **lang:** make the language selector happen sooner in pipeline ([#149](https://github.com/cds-snc/gc-sign-in-migration/issues/149)) ([b79da28](https://github.com/cds-snc/gc-sign-in-migration/commit/b79da28ef230538e4c6992c863fef0ecd77b363f))
* **security:** removed old files not needed includes fornt and backen… ([#150](https://github.com/cds-snc/gc-sign-in-migration/issues/150)) ([aa91da6](https://github.com/cds-snc/gc-sign-in-migration/commit/aa91da662bf43a358b79a8e002b14b880dc4378e))


### Miscellaneous Chores

* **deps:** update all non-major github action dependencies ([adac68b](https://github.com/cds-snc/gc-sign-in-migration/commit/adac68b6ad8560063e758df7d65c9d27ad46c138))
* **deps:** update all non-major github action dependencies ([b97c5b4](https://github.com/cds-snc/gc-sign-in-migration/commit/b97c5b4ad4707ca4dc61d8326bddd2f07c9d4d74))
* **deps:** update dependency fastapi to v0.129.2 ([#155](https://github.com/cds-snc/gc-sign-in-migration/issues/155)) ([4d11c7a](https://github.com/cds-snc/gc-sign-in-migration/commit/4d11c7a1fbba56e2d608574383585e9e96f29fdc))
* **deps:** update dependency fastapi to v0.131.0 ([#156](https://github.com/cds-snc/gc-sign-in-migration/issues/156)) ([555dd8e](https://github.com/cds-snc/gc-sign-in-migration/commit/555dd8e1d0dac3e6b9b64eaf8111c98f6e0a57c5))
* **deps:** update github/codeql-action action to v3.32.4 ([#154](https://github.com/cds-snc/gc-sign-in-migration/issues/154)) ([1c515b3](https://github.com/cds-snc/gc-sign-in-migration/commit/1c515b3164bddb91665dc4cd085934bb9e93c3a3))

## [1.10.1](https://github.com/cds-snc/gc-sign-in-migration/compare/v1.10.0...v1.10.1) (2026-02-26)


### Bug Fixes

* **deps:** added support for multiple RP legacy PAIs ([#130](https://github.com/cds-snc/gc-sign-in-migration/issues/130)) ([2481197](https://github.com/cds-snc/gc-sign-in-migration/commit/2481197fb39e7db88f31fa87ed705ee10aa7023a))
* **lang:** removed some old code from manage profile and language and… ([#145](https://github.com/cds-snc/gc-sign-in-migration/issues/145)) ([71b2b64](https://github.com/cds-snc/gc-sign-in-migration/commit/71b2b6483cc3cdcac524c9a73aa509a4df9172b2))


### Miscellaneous Chores

* **deps:** update all minor dependencies ([#126](https://github.com/cds-snc/gc-sign-in-migration/issues/126)) ([a7476a6](https://github.com/cds-snc/gc-sign-in-migration/commit/a7476a6c3bacd44194081c03ed8f5ce9b59d319d))
* **deps:** update all patch dependencies ([#125](https://github.com/cds-snc/gc-sign-in-migration/issues/125)) ([37db118](https://github.com/cds-snc/gc-sign-in-migration/commit/37db118ff6a3523f921b35b65503e16581350fed))

## [1.10.0](https://github.com/cds-snc/gc-sign-in-migration/compare/v1.9.3...v1.10.0) (2026-02-26)


### Features

* Deploy migration app to staging ([a232099](https://github.com/cds-snc/gc-sign-in-migration/commit/a232099b42ef845a5059a2a5f93d5f193e0c6322))

## [1.9.3](https://github.com/cds-snc/gc-sign-in-migration/compare/v1.9.2...v1.9.3) (2026-02-26)


### Bug Fixes

* **frontend:** Fix None in the path for Link Prompt Page ([#136](https://github.com/cds-snc/gc-sign-in-migration/issues/136)) ([bdbb251](https://github.com/cds-snc/gc-sign-in-migration/commit/bdbb2514aaaee982b3cd0134379f5238164f0207))
* **language:** Feature/possible language toggle fix ([#138](https://github.com/cds-snc/gc-sign-in-migration/issues/138)) ([453ce61](https://github.com/cds-snc/gc-sign-in-migration/commit/453ce61cecc53d4be61f34af0a32507e2c49d7e2))

## [1.9.2](https://github.com/cds-snc/gc-sign-in-migration/compare/v1.9.1...v1.9.2) (2026-02-25)


### Bug Fixes

* **deps:** make the acr values part of the config options. ([#134](https://github.com/cds-snc/gc-sign-in-migration/issues/134)) ([7eb12a9](https://github.com/cds-snc/gc-sign-in-migration/commit/7eb12a98bf5776e03b7c11d1f3f9f816078660d9))

## [1.9.1](https://github.com/cds-snc/gc-sign-in-migration/compare/v1.9.0...v1.9.1) (2026-02-25)


### Bug Fixes

* **deps:** removed menu since not required ([#131](https://github.com/cds-snc/gc-sign-in-migration/issues/131)) ([a3ead22](https://github.com/cds-snc/gc-sign-in-migration/commit/a3ead22b9af663dc114a41ae26c3292d02066958))

## [1.9.0](https://github.com/cds-snc/gc-sign-in-migration/compare/v1.8.0...v1.9.0) (2026-02-20)


### Features

* Reduce healthcheck noise ([aa6ddb9](https://github.com/cds-snc/gc-sign-in-migration/commit/aa6ddb9f8d9a726a87f104ab707b1a0557e18111))
* Reduce healthcheck noise ([6e95856](https://github.com/cds-snc/gc-sign-in-migration/commit/6e9585689f7949042df2d26b0fd3284f685b0611))


### Bug Fixes

* **deps:** update all minor dependencies ([#52](https://github.com/cds-snc/gc-sign-in-migration/issues/52)) ([9ca1b54](https://github.com/cds-snc/gc-sign-in-migration/commit/9ca1b5467388c853356169b5a50460b31487e6de))


### Miscellaneous Chores

* add bug template to repo ([250639a](https://github.com/cds-snc/gc-sign-in-migration/commit/250639af8e02c9f19020dbb5774d6c22c6459558))
* add bug template to repo ([898046d](https://github.com/cds-snc/gc-sign-in-migration/commit/898046df2cce7882e990d218ec9cf8bf61c854c0))
* **deps:** update all patch dependencies ([#45](https://github.com/cds-snc/gc-sign-in-migration/issues/45)) ([d757c22](https://github.com/cds-snc/gc-sign-in-migration/commit/d757c22ceb3385937da0ba8c9239c1ef800678b1))
* **deps:** update dependency authlib to v1.6.6 [security] ([#54](https://github.com/cds-snc/gc-sign-in-migration/issues/54)) ([21c2884](https://github.com/cds-snc/gc-sign-in-migration/commit/21c288456c5990bba3896343865447629c6ddb4d))
* **deps:** update dependency cryptography to v46 [security] ([#100](https://github.com/cds-snc/gc-sign-in-migration/issues/100)) ([f1632fd](https://github.com/cds-snc/gc-sign-in-migration/commit/f1632fdc9626c8cc0365c5fd75c391240184b1c1))
* **deps:** update dependency prettier to v3.8.1 ([#46](https://github.com/cds-snc/gc-sign-in-migration/issues/46)) ([038977f](https://github.com/cds-snc/gc-sign-in-migration/commit/038977f941b4d433520a68a6f21eecb95d9dc1b1))
* **deps:** update dependency python-multipart to v0.0.22 [security] ([#77](https://github.com/cds-snc/gc-sign-in-migration/issues/77)) ([13e066d](https://github.com/cds-snc/gc-sign-in-migration/commit/13e066d4beb371175964a5fe76b0d88792c3096c))
* **deps:** update mcr.microsoft.com/devcontainers/go:bullseye docker digest to 705e1b5 ([#43](https://github.com/cds-snc/gc-sign-in-migration/issues/43)) ([667e94c](https://github.com/cds-snc/gc-sign-in-migration/commit/667e94c3609a9242c3a4cd444c25e0434e5fd7a8))

## [1.8.0](https://github.com/cds-snc/gc-sign-in-migration/compare/v1.7.2...v1.8.0) (2026-02-11)


### Features

* **ci/cd:** Update SSM container image param from CI pipeline ([2244378](https://github.com/cds-snc/gc-sign-in-migration/commit/2244378d47a495e5a41c34a24f0b559707ecdca5))
* **ci/cd:** Update SSM container image param from CI pipeline ([6d45b89](https://github.com/cds-snc/gc-sign-in-migration/commit/6d45b890b47d159c109b06d7646a1df147c18ac8))

## [1.7.2](https://github.com/cds-snc/gc-sign-in-migration/compare/v1.7.1...v1.7.2) (2026-02-10)


### Bug Fixes

* refixed variable name to MIGRATION_SOLUTION_DOMAIN ([#97](https://github.com/cds-snc/gc-sign-in-migration/issues/97)) ([dbba771](https://github.com/cds-snc/gc-sign-in-migration/commit/dbba771c6ea36db8425a4437b111cebfca503e6f))

## [1.7.1](https://github.com/cds-snc/gc-sign-in-migration/compare/v1.7.0...v1.7.1) (2026-02-09)


### Bug Fixes

* Update deploy codeowners with correct teams ([#86](https://github.com/cds-snc/gc-sign-in-migration/issues/86)) ([7d29b7e](https://github.com/cds-snc/gc-sign-in-migration/commit/7d29b7ed04b70a1dd43245c75e15d006a1dcd5f5))

## [1.7.0](https://github.com/cds-snc/gc-sign-in-migration/compare/v1.6.0...v1.7.0) (2026-01-28)


### Features

* Update release pipeline to deploy to dev environment infrastructure ([#64](https://github.com/cds-snc/gc-sign-in-migration/issues/64)) ([b5e820a](https://github.com/cds-snc/gc-sign-in-migration/commit/b5e820ae4bb00e25109680340e3d1867d4ea6030))


### Bug Fixes

* **backend:** 67 migration app remove logging sensitive pii ([#68](https://github.com/cds-snc/gc-sign-in-migration/issues/68)) ([5f1d13d](https://github.com/cds-snc/gc-sign-in-migration/commit/5f1d13d255584db8a743d9e188c28799ebba336f))
* **backend:** fix function variable name confusing ([884aa7a](https://github.com/cds-snc/gc-sign-in-migration/commit/884aa7aa7b00725acaa95a824e9ccaaf2b59bd36))

## Changelog
