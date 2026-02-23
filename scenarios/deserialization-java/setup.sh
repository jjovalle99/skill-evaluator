#!/usr/bin/env bash
set -euo pipefail
cd /workspace

git init -q
git config user.email "test@test.com"
git config user.name "Test"

mkdir -p src/main/java/com/acme/importer

cat > src/main/java/com/acme/importer/UserPreferences.java << 'JAVA'
package com.acme.importer;

import java.io.Serializable;
import java.util.ArrayList;
import java.util.List;

public class UserPreferences implements Serializable {
    private final String username;
    private final List<String> favorites;

    public UserPreferences(String username, List<String> favorites) {
        this.username = username;
        this.favorites = new ArrayList<>(favorites);
    }

    public String getUsername() {
        return username;
    }

    public List<String> getFavorites() {
        return new ArrayList<>(favorites);
    }

    public void normalize() {
        favorites.replaceAll(String::trim);
    }
}
JAVA

cat > src/main/java/com/acme/importer/ImportController.java << 'JAVA'
package com.acme.importer;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

public class ImportController {
    public List<UserPreferences> importCsv(InputStream body) throws IOException {
        List<UserPreferences> imported = new ArrayList<>();
        try (BufferedReader reader = new BufferedReader(
            new InputStreamReader(body, StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                String[] parts = line.split(",", 2);
                if (parts.length < 2) {
                    continue;
                }
                List<String> favorites = List.of(parts[1].split("\\|"));
                imported.add(new UserPreferences(parts[0], favorites));
            }
        }
        return imported;
    }
}
JAVA

git add -A && git commit -q -m "init: profile import controller"

# Add binary import endpoint using unsafe Java deserialization
cat > src/main/java/com/acme/importer/ImportController.java << 'JAVA'
package com.acme.importer;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.ObjectInputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

public class ImportController {
    public List<UserPreferences> importCsv(InputStream body) throws IOException {
        List<UserPreferences> imported = new ArrayList<>();
        try (BufferedReader reader = new BufferedReader(
            new InputStreamReader(body, StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                String[] parts = line.split(",", 2);
                if (parts.length < 2) {
                    continue;
                }
                List<String> favorites = List.of(parts[1].split("\\|"));
                imported.add(new UserPreferences(parts[0], favorites));
            }
        }
        return imported;
    }

    public UserPreferences importSerialized(InputStream payload)
            throws IOException, ClassNotFoundException {
        ObjectInputStream ois = new ObjectInputStream(payload);
        Object decoded = ois.readObject();
        UserPreferences prefs = (UserPreferences) decoded;
        prefs.normalize();
        return prefs;
    }
}
JAVA

git add -A
