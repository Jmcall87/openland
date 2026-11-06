---
name: setup-android-sdk
description: Install JDK 17 and the Android SDK command-line tools inside the OpenLand computer (on demand; not bundled to keep the APK small).
---
# Setup Android SDK

Run this once on the computer (needs network):

```sh
sh /root/setup-android-sdk.sh
```

Then `source /etc/profile.d/android-sdk.sh` (or open a new shell). Verify with `sdkmanager --list` and `javac -version`.
Building an APK: use Gradle in the project, or Capacitor (`npm i @capacitor/cli @capacitor/android && npx cap add android && npx cap sync`).
