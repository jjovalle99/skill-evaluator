#!/usr/bin/env bash
set -euo pipefail
cd /workspace

git init -q
git config user.email "test@test.com"
git config user.name "Test"

mkdir -p src/main/java/com/bank

cat > src/main/java/com/bank/Account.java << 'JAVA'
package com.bank;

public class Account {
    private final long id;
    private long balance;
    private final Object lock = new Object();

    public Account(long id, long balance) {
        this.id = id;
        this.balance = balance;
    }

    public long getId() {
        return id;
    }

    public long getBalance() {
        return balance;
    }

    public void debit(long cents) {
        balance -= cents;
    }

    public void credit(long cents) {
        balance += cents;
    }

    public Object getLock() {
        return lock;
    }
}
JAVA

cat > src/main/java/com/bank/TransferService.java << 'JAVA'
package com.bank;

public class TransferService {
    public void transfer(Account from, Account to, long cents) {
        Object first = from.getId() < to.getId() ? from.getLock() : to.getLock();
        Object second = first == from.getLock() ? to.getLock() : from.getLock();

        synchronized (first) {
            synchronized (second) {
                from.debit(cents);
                to.credit(cents);
            }
        }
    }
}
JAVA

git add -A && git commit -q -m "init: account transfer with consistent lock ordering"

# Add a second transfer path that acquires locks in opposite order
cat > src/main/java/com/bank/TransferService.java << 'JAVA'
package com.bank;

public class TransferService {
    public void transfer(Account from, Account to, long cents) {
        Object first = from.getId() < to.getId() ? from.getLock() : to.getLock();
        Object second = first == from.getLock() ? to.getLock() : from.getLock();

        synchronized (first) {
            synchronized (second) {
                from.debit(cents);
                to.credit(cents);
            }
        }
    }

    public void transferReversal(Account from, Account to, long cents) {
        synchronized (to.getLock()) {
            synchronized (from.getLock()) {
                to.debit(cents);
                from.credit(cents);
            }
        }
    }
}
JAVA

git add -A
