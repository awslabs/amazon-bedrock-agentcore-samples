# Build stage
FROM --platform=linux/arm64 amazoncorretto:21-al2023 AS builder
WORKDIR /app
COPY pom.xml .
COPY src ./src
RUN yum install -y maven && mvn clean package -DskipTests

# Runtime stage
FROM --platform=linux/arm64 amazoncorretto:21-al2023
WORKDIR /app

RUN groupadd -g 1000 agent && useradd -u 1000 -g agent -m agent
USER agent

COPY --from=builder /app/target/*.jar app.jar

EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
