#!/usr/bin/env bash
set -euo pipefail
cd /workspace

git init -q
git config user.email "test@test.com"
git config user.name "Test"

mkdir -p internal/worker

cat > go.mod << 'GOMOD'
module example.com/job-runner

go 1.22
GOMOD

cat > internal/worker/processor.go << 'GO'
package worker

import "fmt"

type Job struct {
	ID      int
	Payload string
}

type Result struct {
	JobID  int
	Output string
}

type jobResult struct {
	result Result
	err    error
}

type Processor struct{}

func (p *Processor) run(job Job) (Result, error) {
	if job.Payload == "" {
		return Result{}, fmt.Errorf("job %d has empty payload", job.ID)
	}
	return Result{JobID: job.ID, Output: "ok:" + job.Payload}, nil
}

func (p *Processor) ProcessAll(jobs []Job) ([]Result, error) {
	resultsCh := make(chan jobResult, len(jobs))
	for _, job := range jobs {
		go func(j Job) {
			out, err := p.run(j)
			resultsCh <- jobResult{result: out, err: err}
		}(job)
	}

	collected := make([]Result, 0, len(jobs))
	for i := 0; i < len(jobs); i++ {
		current := <-resultsCh
		if current.err != nil {
			for pending := i + 1; pending < len(jobs); pending++ {
				<-resultsCh
			}
			return nil, current.err
		}
		collected = append(collected, current.result)
	}
	return collected, nil
}
GO

git add -A && git commit -q -m "init: concurrent processor with safe channel draining"

# Regress to unbuffered result channel and early return without draining
cat > internal/worker/processor.go << 'GO'
package worker

import "fmt"

type Job struct {
	ID      int
	Payload string
}

type Result struct {
	JobID  int
	Output string
}

type jobResult struct {
	result Result
	err    error
}

type Processor struct{}

func (p *Processor) run(job Job) (Result, error) {
	if job.Payload == "" {
		return Result{}, fmt.Errorf("job %d has empty payload", job.ID)
	}
	return Result{JobID: job.ID, Output: "ok:" + job.Payload}, nil
}

func (p *Processor) ProcessAll(jobs []Job) ([]Result, error) {
	resultsCh := make(chan jobResult)
	for _, job := range jobs {
		go func(j Job) {
			out, err := p.run(j)
			resultsCh <- jobResult{result: out, err: err}
		}(job)
	}

	collected := make([]Result, 0, len(jobs))
	for i := 0; i < len(jobs); i++ {
		current := <-resultsCh
		if current.err != nil {
			return nil, current.err
		}
		collected = append(collected, current.result)
	}
	return collected, nil
}
GO

git add -A
