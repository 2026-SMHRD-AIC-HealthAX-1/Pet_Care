package com.smhrd.myapp.domain.monitoring;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import java.io.BufferedReader;
import java.io.File;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;

@Service
@RequiredArgsConstructor
public class MonitoringService {
    private final MonitoringRepository monitoringRepository;

    public String executePythonPipeline() {
        StringBuilder logOutput = new StringBuilder();
        try {
            File rootDir = new File(System.getProperty("user.dir"));
            ProcessBuilder pb = new ProcessBuilder("python", "ai/analyze_pet.py");
            pb.directory(rootDir);
            pb.redirectErrorStream(true);

            Process process = pb.start();

            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    logOutput.append(line).append("\n");
                }
            }

            int exitCode = process.waitFor();
            logOutput.append("\n[Process Terminated with Exit Code: ").append(exitCode).append("]");

        } catch (Exception e) {
            return "Execution Error: " + e.getMessage();
        }
        return logOutput.toString();
    }
}