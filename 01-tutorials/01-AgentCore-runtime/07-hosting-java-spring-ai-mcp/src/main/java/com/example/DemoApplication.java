package com.example;

import org.springaicommunity.mcp.annotation.McpTool;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class DemoApplication {

    @McpTool(description = "add two numbers")
    Integer add(Integer a, Integer b) {
        return a + b;
    }

    public static void main(String[] args) {
        SpringApplication.run(DemoApplication.class, args);
    }
}
