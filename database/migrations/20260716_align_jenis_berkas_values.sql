ALTER TABLE berkas
DROP CONSTRAINT IF EXISTS berkas_jenis_berkas_check;

UPDATE berkas
SET jenis_berkas = CASE jenis_berkas
    WHEN 'PRA_PENUNTUTAN' THEN 'Pra Penuntutan'
    WHEN 'PENUNTUTAN' THEN 'Penuntutan'
    WHEN 'EKSEKUSI' THEN 'Eksekusi'
    ELSE jenis_berkas
END;

ALTER TABLE berkas
ADD CONSTRAINT berkas_jenis_berkas_check
CHECK (jenis_berkas IN ('Pra Penuntutan', 'Penuntutan', 'Eksekusi'));
