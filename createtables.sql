CREATE TABLE Users (
    telegram_id BigInt PRIMARY KEY,
	username VARCHAR(50),
	is_admin BOOLEAN DEFAULT true,
	source VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;    
);

CREATE TABLE check_subscribe (
	id SERIAL PRIMARY KEY,
	user_telegram_id BigInt REFERENCES Users(telegram_id) ON DELETE CASCADE,
	is_subscriber BOOLEAN DEFAULT true,
	
);
CREATE TABLE WB_api_keys (
    id SERIAL PRIMARY KEY,
	name_key VARCHAR(500),  
    user_telegram_id BigInt REFERENCES Users(telegram_id) ON DELETE CASCADE,
    API_KEY VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
);

CREATE TABLE Type_operations (
    id SERIAL PRIMARY KEY,
    type_operation VARCHAR(10)
);

CREATE TABLE Notification (
    id SERIAL PRIMARY KEY,
    wb_api_keys_id BigInt REFERENCES WB_api_keys(id) ON DELETE CASCADE,
    type_operation_id INT REFERENCES Type_Operations(id),
	is_checking BOOLEAN DEFAULT true,
	time_last_in_wb TIMESTAMP
);

CREATE TABLE User_References (
    id SERIAL PRIMARY KEY,
	user_telegram_id BigInt REFERENCES Users(telegram_id) ON DELETE CASCADE,
    ref_user_telegram_id BigInt REFERENCES Users(telegram_id) ON DELETE CASCADE,
);

CREATE TABLE BotSettings (
  id SERIAL PRIMARY KEY,
  on_off BOOLEAN NOT NULL DEFAULT FALSE,
  setting_name VARCHAR(255) NOT NULL,
  setting_description TEXT
);

INSERT INTO Type_Operations (type_operation) VALUES
('Заказы'),
('Продажи'),
('Возвраты');


------------
Чтобы автоматически создавать записи в таблице Notification при добавлении новых записей в WB_api_keys, 
будем использовать триггер или хранимую процедуру в нашей базе данных.

CREATE OR REPLACE FUNCTION add_default_notification() RETURNS TRIGGER AS $$
BEGIN
    -- Для каждого type_operation_id вставляем запись в Notification
    INSERT INTO Notification (wb_api_keys_id, type_operation_id, is_checking)
    SELECT NEW.id, type_operation.id, TRUE
    FROM Type_Operations AS type_operation;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
------------
Чтобы автоматически создавать записи в таблице check_subscribe при регистрации в боте новых пользователей, 
будем использовать триггер или хранимую процедуру в нашей базе данных.
CREATE OR REPLACE FUNCTION add_new_user_to_check_subscribe()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO check_subscribe (user_telegram_id)
  VALUES (NEW.telegram_id);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- Создание триггеров
CREATE TRIGGER insert_user_to_check_subscribe
AFTER INSERT ON Users
FOR EACH ROW
EXECUTE FUNCTION add_new_user_to_check_subscribe();
CREATE TRIGGER trigger_add_default_notification
AFTER INSERT ON WB_api_keys
FOR EACH ROW EXECUTE FUNCTION add_default_notification();