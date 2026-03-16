# Build stage
FROM --platform=linux/arm64 amazoncorretto:21-alpine AS builder
WORKDIR /app
COPY pom.xml .
COPY src ./src
RUN apk add --no-cache maven && mvn clean package -DskipTests

# Runtime stage
FROM --platform=linux/arm64 amazoncorretto:21-alpine
WORKDIR /app

RUN addgroup -g 1000 agent && adduser -u 1000 -G agent -D agent
USER agent

COPY --from=builder /app/target/*.jar app.jar

EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
