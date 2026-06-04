FROM freqtradeorg/freqtrade:stable

WORKDIR /freqtrade

# Copy only the runtime surface. .dockerignore excludes local data, logs, reports,
# secrets and research artifacts.
COPY --chown=ftuser:ftuser user_data/ /freqtrade/user_data/
COPY --chown=ftuser:ftuser dashboard/ /freqtrade/dashboard/
COPY --chown=ftuser:ftuser start.sh /freqtrade/start.sh

USER root
RUN chmod +x /freqtrade/start.sh
USER ftuser

ENV PORT=8092
EXPOSE 8092

ENTRYPOINT ["/freqtrade/start.sh"]
