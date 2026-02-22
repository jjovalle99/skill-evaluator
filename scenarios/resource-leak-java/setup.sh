#!/usr/bin/env bash
set -euo pipefail
cd /workspace

git init -q
git config user.email "test@test.com"
git config user.name "Test"

mkdir -p src/main/java/com/app

cat > src/main/java/com/app/UserRepository.java << 'JAVA'
package com.app;

import java.sql.*;
import java.util.ArrayList;
import java.util.List;

public class UserRepository {
    private final String dbUrl;

    public UserRepository(String dbUrl) {
        this.dbUrl = dbUrl;
    }

    public User findById(long id) throws SQLException {
        try (Connection conn = DriverManager.getConnection(dbUrl);
             PreparedStatement stmt = conn.prepareStatement(
                 "SELECT id, name, email FROM users WHERE id = ?")) {
            stmt.setLong(1, id);
            try (ResultSet rs = stmt.executeQuery()) {
                if (rs.next()) {
                    return new User(rs.getLong("id"), rs.getString("name"), rs.getString("email"));
                }
                return null;
            }
        }
    }

    public List<User> findAll() throws SQLException {
        List<User> users = new ArrayList<>();
        try (Connection conn = DriverManager.getConnection(dbUrl);
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery("SELECT id, name, email FROM users")) {
            while (rs.next()) {
                users.add(new User(rs.getLong("id"), rs.getString("name"), rs.getString("email")));
            }
        }
        return users;
    }
}
JAVA

cat > src/main/java/com/app/User.java << 'JAVA'
package com.app;

public record User(long id, String name, String email) {}
JAVA

git add -A && git commit -q -m "init: user repository with proper resource management"

# Add report exporter that leaks file handles and DB connections
cat > src/main/java/com/app/ReportExporter.java << 'JAVA'
package com.app;

import java.io.*;
import java.sql.*;
import java.util.zip.GZIPOutputStream;

public class ReportExporter {
    private final String dbUrl;

    public ReportExporter(String dbUrl) {
        this.dbUrl = dbUrl;
    }

    public void exportUserReport(String outputPath) throws Exception {
        Connection conn = DriverManager.getConnection(dbUrl);
        Statement stmt = conn.createStatement();
        ResultSet rs = stmt.executeQuery("SELECT id, name, email FROM users");

        FileOutputStream fos = new FileOutputStream(outputPath);
        GZIPOutputStream gzip = new GZIPOutputStream(fos);
        BufferedWriter writer = new BufferedWriter(new OutputStreamWriter(gzip));

        writer.write("id,name,email\n");
        while (rs.next()) {
            writer.write(String.format("%d,%s,%s\n",
                rs.getLong("id"), rs.getString("name"), rs.getString("email")));
        }
        writer.flush();
    }

    public byte[] exportToMemory() throws Exception {
        Connection conn = DriverManager.getConnection(dbUrl);
        Statement stmt = conn.createStatement();
        ResultSet rs = stmt.executeQuery("SELECT id, name, email FROM users");

        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        PrintStream ps = new PrintStream(baos);

        while (rs.next()) {
            ps.printf("%d,%s,%s%n",
                rs.getLong("id"), rs.getString("name"), rs.getString("email"));
        }
        return baos.toByteArray();
    }
}
JAVA
git add -A
